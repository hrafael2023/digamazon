// Parte comum às duas páginas: o topo (data da última pesquisa e, na principal, o
// botão Pesquisar) e a leitura dos discos. Cada página define mostrar(), chamada sempre que os dados mudam.
const REPO = "hrafael2023/digamazon";
const WORKFLOW = "pedido.yml";
const PEDIDO = "digamazon.pedido";
const CHAVE = "digamazon.token";
const API = "https://api.github.com/repos/" + REPO;
const $ = id => document.getElementById(id);
const DIG = 85;  // nota do Metacritic a partir desta ganha o selo "Dig!"
const real = n => n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const capaGrande = foto => foto.replace(/\._AC_[^.]*_\./, "._AC_SL400_.");
let dados = null;

const PESQUISA = !!$("pesquisar");  // só a página principal tem o botão

if (PESQUISA) document.body.insertAdjacentHTML("beforeend", `
<dialog id="dlg-token">
  <h3>Liberar a pesquisa por este celular</h3>
  <p class="nota" style="margin:0">O botão deixa um pedido no GitHub, que o Mac atende. Para isso, crie uma chave uma única vez:</p>
  <ol>
    <li>Abra <a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">github.com/settings/personal-access-tokens/new</a></li>
    <li>Em <b>Repository access</b>, escolha <b>Only select repositories</b> → <b>digamazon</b></li>
    <li>Em <b>Permissions</b>, dê <b>Actions: Read and write</b> e <b>Contents: Read-only</b></li>
    <li>Gere e cole a chave aqui</li>
  </ol>
  <input id="token" type="password" placeholder="github_pat_…" autocomplete="off">
  <p class="nota">A chave fica guardada só neste aparelho e só é enviada ao GitHub.</p>
  <div class="acoes">
    <button type="button" id="cancelar">Cancelar</button>
    <button type="button" class="principal" id="salvar">Salvar e pesquisar</button>
  </div>
</dialog>`);

function guardado(k, v) {
  try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { return null; }
}

function status(texto, erro) { $("status").textContent = texto || ""; $("status").classList.toggle("erro", !!erro); }

function quando(iso) {
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function exibir(novos) {
  dados = novos;
  $("sub").innerHTML = `atualizado <span class="data">${quando(dados.atualizado)}</span>`;
  mostrar();
}

async function carregar() {
  const r = await fetch("dados.json?t=" + Date.now(), { cache: "no-store" });
  if (!r.ok) throw new Error("não consegui abrir os dados (" + r.status + ")");
  exibir(await r.json());
}

function rodando(sim, texto) {
  $("pesquisar").disabled = sim;
  $("pesquisar").classList.toggle("rodando", sim);
  $("rotulo").textContent = sim ? (texto || "Pesquisando") : "Pesquisar";
}

async function gh(caminho, opcoes = {}) {
  const r = await fetch(API + caminho, { ...opcoes, headers: {
    "Accept": "application/vnd.github+json",
    "Authorization": "Bearer " + guardado(CHAVE),
    "X-GitHub-Api-Version": "2022-11-28",
    ...(opcoes.headers || {}) } });
  if (!r.ok) {
    const msg = await r.json().then(j => j.message).catch(() => "");
    const e = new Error(`GitHub respondeu ${r.status}${msg ? ": " + msg : ""}`);
    e.chave = r.status === 401;  // chave inválida ou expirada; 403/404 costumam ser permissão faltando
    e.github = true;
    throw e;
  }
  return r.status === 204 ? null : r.json();
}

const espera = ms => new Promise(r => setTimeout(r, ms));

async function arquivo(nome) {
  // Lê direto do repositório (o Pages leva um minuto para republicar).
  return gh(`/contents/${nome}?ref=main&t=${Date.now()}`, { headers: { "Accept": "application/vnd.github.raw+json" } });
}

async function acompanhar(desde) {
  // O pedido vira uma execução do workflow; o Mac a atende e conta o andamento em estado.json.
  let run, inicio = Date.now();
  for (;;) {
    run = (await gh(`/actions/workflows/${WORKFLOW}/runs?per_page=1&event=workflow_dispatch`)).workflow_runs[0];
    if (run && new Date(run.created_at) >= desde) break;
    if (Date.now() - inicio > 60000) throw new Error("o pedido não chegou ao GitHub; tente de novo");
    await espera(4000);
  }
  guardado(PEDIDO, String(run.id));
  for (;;) {
    const e = await arquivo("estado.json");
    const min = Math.floor((Date.now() - new Date(run.created_at)) / 60000);
    if (e.pedido >= run.id && e.estado === "ok") break;
    if (e.pedido >= run.id && e.estado === "erro") { guardado(PEDIDO, null); throw new Error("A pesquisa falhou no Mac: " + e.mensagem); }
    if (e.pedido >= run.id) status(`O Mac está pesquisando na Amazon… ${min} min (leva uns 5). Pode fechar a página e voltar depois.`);
    else status(min < 3
      ? "Pedido enviado. Esperando o Mac pegar (ele confere a cada 2 minutos)…"
      : `Esperando o Mac há ${min} min. Ele precisa estar ligado e acordado; o pedido fica guardado até lá.`);
    await espera(15000);
  }
  guardado(PEDIDO, null);
  exibir(await arquivo("dados.json"));
  status(dados.novos.length ? `Pronto: ${dados.novos.length} discos novos.` : "Pronto: nenhum disco novo desta vez.");
}

async function pesquisar() {
  if (!guardado(CHAVE)) { $("dlg-token").showModal(); return; }
  rodando(true, "Enviando");
  try {
    const desde = new Date(Date.now() - 5000);
    await gh(`/actions/workflows/${WORKFLOW}/dispatches`, { method: "POST", body: JSON.stringify({ ref: "main" }) });
    rodando(true);
    await acompanhar(desde);
  } catch (e) {
    if (e.chave) { guardado(CHAVE, null); status("O GitHub recusou a chave. Toque em Pesquisar para cadastrar outra.", true); }
    else if (e.github) status(e.message + ". Confira se a chave tem Actions: Read and write e Contents: Read-only no repositório digamazon.", true);
    else status(e.message, true);
  } finally { rodando(false); }
}

async function retomar() {
  // Se a página foi fechada com um pedido em andamento, continua acompanhando.
  const id = guardado(PEDIDO);
  if (!guardado(CHAVE) || !id) return;
  rodando(true);
  try {
    const run = await gh(`/actions/runs/${id}`);
    await acompanhar(new Date(run.created_at));
  } catch (e) { status(e.message, true); }
  finally { rodando(false); }
}

if (PESQUISA) {
  $("pesquisar").addEventListener("click", pesquisar);
  $("cancelar").addEventListener("click", () => $("dlg-token").close());
  $("salvar").addEventListener("click", () => {
    const t = $("token").value.trim();
    if (!t) return;
    guardado(CHAVE, t); $("token").value = ""; $("dlg-token").close(); pesquisar();
  });
}

// Chamada pela página depois de definir mostrar().
function iniciar() { carregar().then(() => PESQUISA && retomar()).catch(e => status(e.message, true)); }
