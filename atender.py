#!/usr/bin/env python3
"""Atende os pedidos do botão Dig, rodando a busca neste Mac.

O botão da página dispara o workflow pedido.yml no GitHub. Este script
(chamado a cada 2 minutos pelo agendamento do macOS) confere se há pedido
novo; se houver, roda buscar.py e envia dados.json para o repositório, o
que republica a página. estado.json conta para a página em que pé está.

Uso:
    python3 atender.py          # confere e atende um pedido pendente
    ./instalar-agendamento.sh   # deixa conferindo a cada 2 minutos
"""

import datetime as dt
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import buscar

PASTA = Path(__file__).resolve().parent
ESTADO = PASTA / "estado.json"
# Último pedido atendido; fica só neste Mac.
ULTIMO = PASTA / ".ultimo-pedido"
PEDIDOS = ("https://api.github.com/repos/hrafael2023/digamazon/actions/workflows/"
           "pedido.yml/runs?event=workflow_dispatch&per_page=5")


def log(msg):
    print(f"{dt.datetime.now():%d/%m %H:%M:%S} {msg}", flush=True)


def git(*args):
    subprocess.run(["git", "-C", str(PASTA), *args], check=True, capture_output=True, text=True)


def ultimo_pedido():
    pedido = urllib.request.Request(PEDIDOS, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(pedido, timeout=20) as r:
        runs = json.load(r)["workflow_runs"]
    return max((run["id"] for run in runs), default=0)


def enviar(arquivos, mensagem):
    git("add", *arquivos)
    git("commit", "-m", mensagem)
    git("push", "-q", "origin", "main")


def marcar(pedido, estado, mensagem=""):
    ESTADO.write_text(json.dumps({
        "pedido": pedido,
        "estado": estado,
        "mensagem": mensagem,
        "quando": dt.datetime.now(buscar.FUSO).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=1) + "\n")


def main():
    try:
        pedido = ultimo_pedido()
    except OSError as e:
        log(f"sem acesso ao GitHub: {e}")
        return
    if not ULTIMO.exists():
        # Primeira vez: começa a contar a partir de agora, sem atender pedidos antigos.
        ULTIMO.write_text(str(pedido))
        log(f"começando a partir do pedido {pedido}")
        return
    if pedido <= int(ULTIMO.read_text() or 0):
        return

    log(f"pedido {pedido}: pesquisando")
    ULTIMO.write_text(str(pedido))
    git("pull", "-q", "--rebase", "origin", "main")
    marcar(pedido, "buscando")
    enviar(["estado.json"], "Pesquisa em andamento")

    try:
        total, novos = buscar.buscar()
    except buscar.Falhou as e:
        log(f"pedido {pedido}: {e}")
        marcar(pedido, "erro", str(e))
        enviar(["estado.json"], "Pesquisa falhou")
        sys.exit(1)

    resumo = f"{total} discos, {novos} novos"
    log(f"pedido {pedido}: {resumo}")
    marcar(pedido, "ok", resumo)
    enviar(["dados.json", "vistos.json", "notas.json", "estado.json"],
           f"Atualiza os discos ({dt.datetime.now(buscar.FUSO):%d/%m %H:%M}): {resumo}")


if __name__ == "__main__":
    main()
