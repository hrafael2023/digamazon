# DigAmazon

Vinis da Amazon.com.br abaixo de R$ 150, numa página para abrir no celular:
https://hrafael2023.github.io/digamazon/

- `buscar.py` percorre a lista de discos de vinil ordenada por preço e grava
  `dados.json` (lista completa e discos novos na faixa) e `vistos.json`
  (quando cada disco apareceu pela primeira vez).
- `.github/workflows/buscar.yml` roda a busca todo dia às 13h e quando o botão
  **Pesquisar** da página é tocado, e publica a página no GitHub Pages.
- O botão precisa de uma chave do GitHub (fine-grained, só este repositório,
  permissão *Actions: Read and write*), cadastrada uma vez em cada aparelho.
