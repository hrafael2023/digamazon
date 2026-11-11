#!/usr/bin/env python3
"""Roda a busca automática do DigAmazon uma vez por dia, de madrugada, neste Mac.

O agendamento do macOS chama este script a cada 2 minutos. Ele só busca a
partir das 5h e só uma vez por dia; se a Amazon bloquear, tenta de novo mais
tarde (até TENTATIVAS vezes, com HORAS_ENTRE horas de intervalo). Ao terminar,
envia dados.json ao repositório, o que republica a página. estado.json conta à
página em que pé está a busca.

Uso:
    python3 atender.py          # busca, se for hora
    ./instalar-agendamento.sh   # deixa conferindo a cada 2 minutos
"""

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import buscar

PASTA = Path(__file__).resolve().parent
ESTADO = PASTA / "estado.json"
# Tentativas do dia; fica só neste Mac.
TENTATIVAS_ARQ = PASTA / ".tentativas"

HORA = 5            # a busca do dia começa a partir das 5h
TENTATIVAS = 3      # se falhar: tenta de novo...
HORAS_ENTRE = 2     # ...depois de 2 horas (por volta das 7h e das 9h)


def log(msg):
    print(f"{dt.datetime.now():%d/%m %H:%M:%S} {msg}", flush=True)


def agora():
    return dt.datetime.now(buscar.FUSO)


def git(*args):
    r = subprocess.run(["git", "-C", str(PASTA), *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"git {args[0]} falhou: {(r.stderr or r.stdout).strip()}")
    return r.stdout


def enviar(arquivos, mensagem):
    git("add", *arquivos)
    git("commit", "-m", mensagem)
    publicar()


def publicar():
    """Envia os commits ao GitHub; a rede às vezes falha, então tenta algumas vezes."""
    for espera in [10, 30, 60, None]:
        try:
            git("push", "-q", "origin", "main")
            return True
        except RuntimeError as e:
            log(str(e))
            if espera is None:
                return False  # fica para a próxima rodada, daqui a 2 minutos
            time.sleep(espera)
            try:
                git("pull", "-q", "--rebase", "origin", "main")
            except RuntimeError as e:
                log(str(e))


def pendente():
    """Há commits deste Mac que ainda não chegaram ao GitHub?"""
    try:
        git("fetch", "-q", "origin", "main")
        return int(git("rev-list", "--count", "origin/main..main").strip() or 0) > 0
    except RuntimeError as e:
        log(str(e))
        return False


def marcar(estado, mensagem="", **progresso):
    ESTADO.write_text(json.dumps({
        "estado": estado,
        "mensagem": mensagem,
        "quando": agora().isoformat(timespec="seconds"),
        **progresso,
    }, ensure_ascii=False, indent=1) + "\n")


# A cada tantas páginas o Mac conta à página como vai a busca. Cada aviso é um
# commit de estado.json, por isso não a cada página.
AVISAR_A_CADA = 10


def acompanhante(inicio):
    """Devolve a função que buscar.buscar() chama a cada passo, e que avisa a página."""
    try:
        previstas = json.loads(buscar.DADOS.read_text()).get("paginas") or 75
    except (OSError, ValueError):
        previstas = 75
    ultima = {"etapa": None}

    def progresso(etapa, pagina=0, discos=0, mensagem=""):
        # Depois de uma espera, avisa logo que voltou a andar.
        if etapa == "buscando" and pagina % AVISAR_A_CADA and ultima["etapa"] != "esperando":
            return
        ultima["etapa"] = etapa
        marcar("buscando", mensagem, etapa=etapa, pagina=pagina, previstas=max(previstas, pagina),
               discos=discos, inicio=inicio)
        try:
            git("add", "estado.json")
            git("commit", "-q", "-m", f"Pesquisa em andamento: página {pagina} de ~{previstas}")
            git("push", "-q", "origin", "main")
        except RuntimeError as e:
            log(str(e))  # o aviso é só para acompanhar; a busca segue mesmo sem ele
    return progresso


def ler(arquivo):
    try:
        return json.loads(arquivo.read_text())
    except (OSError, ValueError):
        return {}


def interrompida():
    """Início da busca que parou sem terminar (o Mac reiniciou ou desligou no meio), ou None.

    O macOS não roda este script duas vezes ao mesmo tempo, então se estado.json
    ainda diz "buscando" quando ele começa, aquela busca morreu. Se faz pouco
    tempo, ela é retomada; se faz muito, a página passa a mostrar o erro.
    """
    e = ler(ESTADO)
    if e.get("estado") != "buscando":
        return None
    if agora() - dt.datetime.fromisoformat(e["quando"]) < buscar.RETOMAR_ATE:
        return e.get("inicio") or e["quando"]
    log("a busca parou no meio há muitas horas")
    marcar("erro", "a busca parou no meio (o Mac desligou ou reiniciou)")
    enviar(["estado.json"], "Pesquisa interrompida")
    return None


def hora_de_buscar():
    """Já passou das 5h e a busca de hoje ainda não deu certo nem esgotou as tentativas?"""
    hoje = agora().date().isoformat()
    t = ler(TENTATIVAS_ARQ)
    if not t:
        # Primeira vez: começa amanhã, sem buscar já.
        TENTATIVAS_ARQ.write_text(json.dumps({"dia": hoje, "vezes": TENTATIVAS, "ok": True}))
        log("busca automática ligada; a primeira é amanhã a partir das 5h")
        return False
    if agora().hour < HORA:
        return False
    if t.get("dia") != hoje:
        return True
    if t.get("ok") or t.get("vezes", 0) >= TENTATIVAS:
        return False
    ultima = dt.datetime.fromisoformat(t["ultima"])
    return agora() - ultima >= dt.timedelta(hours=HORAS_ENTRE)


def contar_tentativa(ok=False):
    hoje = agora().date().isoformat()
    t = ler(TENTATIVAS_ARQ)
    if t.get("dia") != hoje:
        t = {"dia": hoje, "vezes": 0}
    if ok:
        t["ok"] = True
    else:
        t["vezes"] = t.get("vezes", 0) + 1
        t["ultima"] = agora().isoformat(timespec="seconds")
    TENTATIVAS_ARQ.write_text(json.dumps(t))
    return t


def main():
    if pendente():
        log("enviando resultado que tinha ficado sem chegar ao GitHub")
        publicar()

    inicio = interrompida()
    if inicio:
        log("a busca tinha parado no meio (o Mac desligou ou reiniciou); retomando")
    elif hora_de_buscar():
        inicio = agora().isoformat(timespec="seconds")
        contar_tentativa()
        log("busca automática: pesquisando")
    else:
        return

    # Não deixa o Mac dormir enquanto este script estiver rodando.
    subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])

    try:
        git("pull", "-q", "--rebase", "origin", "main")
    except RuntimeError as e:
        log(str(e))
    progresso = acompanhante(inicio)
    progresso("buscando")
    try:
        total, novos = buscar.buscar(progresso)
    except buscar.Falhou as e:
        t = ler(TENTATIVAS_ARQ)
        de_novo = t.get("vezes", 0) < TENTATIVAS
        mensagem = str(e) + (f". O Mac tenta de novo daqui a {HORAS_ENTRE} horas." if de_novo
                             else ". O Mac tenta de novo amanhã às 5h.")
        log(mensagem)
        marcar("erro", mensagem)
        enviar(["estado.json"], "Pesquisa falhou")
        sys.exit(1)

    contar_tentativa(ok=True)
    resumo = f"{total} discos, {novos} novos"
    log(f"busca automática: {resumo}")
    marcar("ok", resumo)
    enviar(["dados.json", "vistos.json", "notas.json", "estado.json"],
           f"Atualiza os discos ({agora():%d/%m %H:%M}): {resumo}")


if __name__ == "__main__":
    main()
