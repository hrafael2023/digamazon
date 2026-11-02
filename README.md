# DigAmazon

Vinis da Amazon.com.br abaixo de R$ 150, numa página para abrir no celular:
https://hrafael2023.github.io/digamazon/

A Amazon recusa buscas vindas dos servidores do GitHub, então a busca roda no Mac:

1. O botão **Pesquisar** da página dispara o workflow `pedido.yml`, que só registra o pedido.
2. No Mac, `atender.py` confere a cada 2 minutos se há pedido novo. Se houver, roda
   `buscar.py` e envia `dados.json` (lista completa e discos novos na faixa),
   `vistos.json` (quando cada disco apareceu pela primeira vez) e `estado.json`
   (andamento, que a página acompanha).
3. Para cada disco novo, `notas.py` procura a nota da crítica no Metacritic (guardada em
   `notas.json`); acima de 85, a capa ganha o selo **Dig!**.
4. O workflow `publicar.yml` republica a página quando `dados.json` ou `index.html` mudam.

Para o Mac começar a conferir os pedidos: `./instalar-agendamento.sh`
(para parar: `./instalar-agendamento.sh --remover`). O Mac precisa estar ligado e acordado.

O botão precisa de uma chave do GitHub (fine-grained, só este repositório,
*Actions: Read and write* e *Contents: Read-only*), cadastrada uma vez em cada aparelho.
