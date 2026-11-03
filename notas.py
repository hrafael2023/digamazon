#!/usr/bin/env python3
"""Notas da crítica para os discos, pelo Metacritic.

Para os discos do selo, procura também a página do álbum no Bandcamp,
para escutar antes de comprar.

O Metacritic reúne as críticas de vários sites (Pitchfork, AllMusic e
outros) numa nota de 0 a 100. Album of the Year e AllMusic bloqueiam
acesso automático, por isso ficam de fora. Cada disco é procurado uma vez
e o resultado fica em notas.json; quem não foi achado é procurado de novo
depois de um mês, porque o disco pode ter ganhado críticas.

Uso:
    python3 notas.py      # procura as notas dos discos de dados.json
"""

import datetime as dt
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

PASTA = Path(__file__).resolve().parent
NOTAS = PASTA / "notas.json"
DIG = 85  # nota a partir desta ganha o selo "Dig!"
REVER_DEPOIS = dt.timedelta(days=30)
BANDCAMP = "https://bandcamp.com/api/bcsearch_public_api/1/autocomplete_elastic"
BUSCA = "https://backend.metacritic.com/finder/metacritic/search/{q}/web?offset=0&limit=10&mcoTypeId=31"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
# Palavras que a Amazon junta ao nome do disco e não fazem parte dele.
SOBRAS = {"lp", "2lp", "3lp", "vinyl", "vinil", "disco", "de", "edition", "deluxe", "remastered",
          "remaster", "anniversary", "expanded", "180g", "180", "gram", "colored", "color",
          "limited", "the", "a", "and", "e", "o", "ep", "single", "reissue", "black"}


def normal(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = texto.lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texto).split())


# Complementos entre colchetes ou parênteses que descrevem o vinil, não o disco.
FORMATO = re.compile(r"vinyl|vinil|vinilo|\blp\b|\b\d?lp\b|edition|explicit|parental|reissue|remaster|"
                     r"colou?r|single|deluxe|import|\b180|gram|\bcd\b|limited|splatter|clear|\bep\b", re.I)


def limpar(titulo):
    """Tira do título da Amazon os complementos de formato: [Clear LP], (Blue Vinyl)..."""
    return re.sub(r"\[[^\]]*\]|\([^)]*\)", lambda m: " " if FORMATO.search(m.group()) else m.group(), titulo)


def limpar_mc(titulo, ano=""):
    # No Metacritic, os colchetes trazem [EP], [Live], [Box Set] ou o ano, que separa
    # discos de mesmo nome ("Weezer [2001]"); o ano só sai se for o mesmo da Amazon.
    return re.sub(r"\[([^\]]*)\]",
                  lambda m: m.group(1) if re.fullmatch(r"\d{4}", m.group(1)) and m.group(1) != ano else " ",
                  titulo)


def artista_de(disco):
    a = disco["artista"]
    if re.fullmatch(r"[^,\s][^,]*,[^,\s][^,]*", a):  # "CASSIDY,SHAUN" → "SHAUN CASSIDY"
        sobrenome, nome = a.split(",")
        a = f"{nome} {sobrenome}"
    return a


def casa(disco, item):
    """O resultado do Metacritic é este disco? Exige artista e nome batendo."""
    texto = normal(artista_de(disco) + " " + limpar(disco["titulo"]))
    artista = normal(" ".join(a["name"] for a in item.get("artists") or []))
    album = normal(limpar_mc(item["title"], disco.get("ano", "")))
    if not artista or len(album) < 2:
        return False
    if f" {artista} " not in f" {texto} " or f" {album} " not in f" {texto} ":
        return False
    sobra = f" {texto} ".replace(f" {artista} ", " ", 1).replace(f" {album} ", " ", 1).split()
    return not [p for p in sobra if p not in SOBRAS]


def procurar(disco):
    q = f"{artista_de(disco)} {limpar(disco['titulo'])}"
    q = " ".join(q.split())[:80]
    pedido = urllib.request.Request(BUSCA.format(q=urllib.parse.quote(q)), headers={"User-Agent": UA})
    with urllib.request.urlopen(pedido, timeout=40) as r:
        itens = json.load(r)["data"]["items"]
    for item in itens:
        if item.get("type") != "music-album":
            continue
        nota = (item.get("criticScoreSummary") or {}).get("score")
        if nota and casa(disco, item):
            return {
                "nota": nota,
                "album": item["title"],
                "artista": ", ".join(a["name"] for a in item.get("artists") or []),
                "url": "https://www.metacritic.com" + item["criticScoreSummary"]["url"],
            }
    return None


def no_bandcamp(disco):
    """Endereço do álbum no Bandcamp, se algum resultado casar com o disco."""
    q = " ".join(f"{artista_de(disco)} {limpar(disco['titulo'])}".split())[:80]
    corpo = json.dumps({"search_text": q, "search_filter": "a", "full_page": False, "fan_id": None}).encode()
    pedido = urllib.request.Request(BANDCAMP, data=corpo, headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=40) as r:
        itens = json.load(r)["auto"]["results"]
    for item in itens:
        if item.get("type") == "a" and casa(disco, {"artists": [{"name": item["band_name"]}], "title": item["name"]}):
            return item["item_url_path"]
    return None


def vencido(quando, agora):
    return agora - dt.datetime.fromisoformat(quando) > REVER_DEPOIS


def escutar(discos, notas, agora, mostrar):
    """Acha no Bandcamp os discos do selo que ainda não foram procurados lá."""
    faltam = [d for d in discos if (notas.get(d["asin"], {}).get("nota") or 0) >= DIG
              and ("bandcamp" not in notas[d["asin"]]
                   or (notas[d["asin"]]["bandcamp"] is None and vencido(notas[d["asin"]]["bandcamp_quando"], agora)))]
    if faltam:
        mostrar(f"procurando {len(faltam)} discos no Bandcamp")
    for d in faltam:
        try:
            url = no_bandcamp(d)
        except (OSError, ValueError, KeyError) as e:
            mostrar(f"Bandcamp falhou ({e}); continua na próxima pesquisa")
            break
        notas[d["asin"]].update(bandcamp=url, bandcamp_quando=agora.isoformat(timespec="minutes"))
        time.sleep(1)


def atualizar(discos, mostrar=print):
    """Procura as notas que faltam e devolve {asin: nota} dos discos achados."""
    notas = json.loads(NOTAS.read_text()) if NOTAS.exists() else {}
    agora = dt.datetime.now()
    faltam = [d for d in discos if d["asin"] not in notas
              or (notas[d["asin"]].get("nota") is None
                  and vencido(notas[d["asin"]]["quando"], agora))]
    if faltam:
        mostrar(f"procurando notas de {len(faltam)} discos no Metacritic")
    erros = 0  # seguidos; uma falha solta só deixa o disco para a próxima pesquisa
    for n, d in enumerate(faltam, 1):
        try:
            achado = procurar(d)
            erros = 0
        except (OSError, ValueError, KeyError) as e:
            erros += 1
            if erros >= 5:
                mostrar(f"Metacritic falhou {erros} vezes seguidas ({e}); continua na próxima pesquisa")
                break
            time.sleep(5)
            continue
        notas[d["asin"]] = {**(achado or {"nota": None}), "quando": agora.isoformat(timespec="minutes")}
        if n % 50 == 0:
            NOTAS.write_text(json.dumps(notas, ensure_ascii=False, indent=0, sort_keys=True) + "\n")
            mostrar(f"  {n}/{len(faltam)}")
        time.sleep(1)
    escutar(discos, notas, agora, mostrar)
    NOTAS.write_text(json.dumps(notas, ensure_ascii=False, indent=0, sort_keys=True) + "\n")
    return {a: n for a, n in notas.items() if n.get("nota") is not None}


def main():
    import buscar
    dados = json.loads(buscar.DADOS.read_text())
    achados = atualizar(dados["discos"])
    buscar.anotar(dados["discos"], achados, json.loads(buscar.VISTOS.read_text()))
    buscar.DADOS.write_text(json.dumps(dados, ensure_ascii=False, indent=0) + "\n")
    dig = sum(1 for d in dados["discos"] if d.get("nota", 0) >= DIG)
    print(f"{len(achados)} discos com nota, {dig} de {DIG} ou mais")


if __name__ == "__main__":
    sys.exit(main())
