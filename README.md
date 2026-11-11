# DigAmazon

Vinis da Amazon.com.br abaixo de R$ 150, numa página para abrir no celular:
https://hrafael2023.github.io/digamazon/

A Amazon recusa buscas vindas dos servidores do GitHub, então a busca roda no Mac,
sozinha, uma vez por dia:

1. No Mac, `atender.py` roda a cada 2 minutos e, a partir das 5h, faz a busca do dia.
   Se a Amazon bloquear, tenta de novo 2 horas depois (até 3 vezes no dia).
2. A busca roda `buscar.py` e envia `dados.json` (lista completa e discos novos na faixa),
   `vistos.json` (quando cada disco apareceu pela primeira vez) e `estado.json`
   (andamento, que a página mostra se for aberta durante a busca).
3. Para cada disco novo, `notas.py` procura a nota da crítica no Metacritic (guardada em
   `notas.json`); com 85 ou mais, a capa ganha o selo **Dig!** e o disco entra na página **Dig! Discover** (`dig.html`), com um botão Escutar que abre o álbum no Bandcamp.
4. O workflow `publicar.yml` republica a página quando `dados.json` ou `index.html` mudam.

Para o Mac começar a buscar sozinho: `./instalar-agendamento.sh`
(para parar: `./instalar-agendamento.sh --remover`).

Para a busca rodar de madrugada, o Mac precisa acordar às 5h, na tomada e com a tampa
aberta (a tela pode ficar apagada). Isso se configura uma vez no Terminal:

    sudo pmset repeat wakeorpoweron MTWRFSU 05:00:00

(para desfazer: `sudo pmset repeat cancel`). Enquanto a busca roda, o próprio script
impede o Mac de voltar a dormir. Se ele estiver desligado às 5h, a busca roda quando
for ligado.
