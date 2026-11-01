#!/usr/bin/env python3
"""DigAmazon: vinis da Amazon.com.br abaixo de R$ 150.

Percorre a lista de discos de vinil ordenada por preço (do menor para o
maior) até passar do limite, e grava dados.json com a lista completa e os
discos que entraram na faixa nesta busca (os que nunca tinham aparecido em
vistos.json).

Uso:
    python3 buscar.py
"""

import datetime as dt
import gzip
import html
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados.json"
# ASIN → quando o disco apareceu pela primeira vez abaixo do limite.
VISTOS = PASTA / "vistos.json"
LIMITE = 150.0
MAX_PAGINAS = 150
URL = ("https://www.amazon.com.br/s?i=popular&rh=n%3A19549018011"
       "&s=price-asc-rank&fs=true&page={pagina}")
CABECALHOS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
    "Accept-Encoding": "gzip",
}
FUSO = dt.timezone(dt.timedelta(hours=-3))


class Bloqueado(Exception):
    pass


def avisar(msg, nivel="warning"):
    # No GitHub Actions, vira uma anotação visível na página da execução.
    print(f"::{nivel}::{msg}" if os.environ.get("GITHUB_ACTIONS") else msg, file=sys.stderr)


def baixar(pagina):
    pedido = urllib.request.Request(URL.format(pagina=pagina), headers=CABECALHOS)
    with urllib.request.urlopen(pedido, timeout=30) as r:
        corpo = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            corpo = gzip.decompress(corpo)
    texto = corpo.decode("utf-8", "replace")
    if "validateCaptcha" in texto or "/errors/validateCaptcha" in texto:
        raise Bloqueado(f"captcha na página {pagina}")
    if 's-search-result' not in texto:
        raise Bloqueado(f"página {pagina} veio sem resultados")
    return texto


def baixar_com_paciencia(pagina, tentativas=4):
    for n in range(tentativas):
        try:
            return baixar(pagina)
        except (Bloqueado, OSError) as e:
            if n == tentativas - 1:
                raise
            espera = 10 * (n + 1)
            avisar(f"{e}; tentando de novo em {espera}s")
            time.sleep(espera)


def valor(texto):
    return float(texto.replace("R$", "").replace("\xa0", "").strip()
                 .replace(".", "").replace(",", "."))


def extrair(texto):
    """Devolve os discos da página: [{asin, titulo, artista, ano, preco, foto}]."""
    discos = []
    # Cada resultado começa num <div> com data-asin e data-component-type="s-search-result".
    for bloco in re.split(r'(?=<div[^>]*data-component-type="s-search-result")', texto)[1:]:
        if "AdHolder" in bloco[:bloco.find(">")]:
            continue  # anúncio patrocinado, fora da ordem de preço
        asin = re.match(r'<div[^>]*data-asin="(\w{10})"', bloco)
        titulo = re.search(r'<h2[^>]*aria-label="([^"]*)"', bloco)
        # O primeiro preço "xl" é o do formato vinil; os seguintes são outros formatos.
        preco = re.search(r'<span class="a-price" data-a-size="xl"[^>]*>'
                          r'<span class="a-offscreen">([^<]*)', bloco)
        if not (asin and titulo and preco):
            continue
        foto = re.search(r'class="s-image" src="([^"]*)"', bloco)
        artista = re.search(r'>por </span>.*?<span class="a-size-base[^"]*"[^>]*>([^<]+)<', bloco, re.S)
        ano = re.search(r'<span class="a-size-base a-color-secondary a-text-normal">((?:19|20)\d\d)<', bloco)
        nome = html.unescape(titulo.group(1)).replace("[Disco de Vinil]", "").strip()
        artista = html.unescape(artista.group(1)).strip() if artista else ""
        # Muitos títulos vêm como "Artista, Disco"; o artista já aparece embaixo.
        if artista and nome.lower().startswith(artista.lower() + ", "):
            nome = nome[len(artista) + 2:]
        discos.append({
            "asin": asin.group(1),
            "titulo": nome,
            "artista": artista,
            "ano": ano.group(1) if ano else "",
            "preco": valor(html.unescape(preco.group(1))),
            "foto": foto.group(1) if foto else "",
        })
    return discos


def coletar():
    achados = {}
    acima = 0
    for pagina in range(1, MAX_PAGINAS + 1):
        try:
            discos = extrair(baixar_com_paciencia(pagina))
        except Exception as e:
            raise RuntimeError(f"{e} (depois de {len(achados)} discos)") from e
        if not discos:
            break
        for d in discos:
            if d["preco"] < LIMITE and d["asin"] not in achados:
                achados[d["asin"]] = d
        menor = min(d["preco"] for d in discos)
        print(f"página {pagina}: {len(discos)} discos, menor R$ {menor:.2f}, total {len(achados)}")
        # A ordenação da Amazon não é exata, então só para depois de duas páginas inteiras acima do limite.
        acima = acima + 1 if menor >= LIMITE else 0
        if acima >= 2:
            break
        time.sleep(2)
    return achados


class Falhou(Exception):
    pass


def buscar():
    """Faz a busca e grava os arquivos; devolve (discos, novos) ou levanta Falhou."""
    vistos = json.loads(VISTOS.read_text()) if VISTOS.exists() else {}
    primeira = not vistos

    try:
        achados = coletar()
    except Exception as e:
        raise Falhou(f"busca interrompida: {e}") from e
    if len(achados) < 50:
        raise Falhou(f"só {len(achados)} discos: provavelmente bloqueado, mantendo os dados antigos")

    agora = dt.datetime.now(FUSO).isoformat(timespec="minutes")
    for asin in achados:
        vistos.setdefault(asin, agora)
    discos = sorted(achados.values(), key=lambda d: d["preco"])
    novos = [] if primeira else [d for d in discos if vistos[d["asin"]] == agora]

    VISTOS.write_text(json.dumps(vistos, indent=0, sort_keys=True) + "\n")
    DADOS.write_text(json.dumps({
        "atualizado": agora,
        "limite": LIMITE,
        "primeira": primeira,
        "novos": [d["asin"] for d in novos],
        "discos": discos,
    }, ensure_ascii=False, indent=0) + "\n")
    return len(discos), len(novos)


def main():
    try:
        total, novos = buscar()
    except Falhou as e:
        avisar(str(e), "error")
        sys.exit(1)
    avisar(f"{total} discos abaixo de R$ {LIMITE:.0f}, {novos} novos", "notice")


if __name__ == "__main__":
    main()
