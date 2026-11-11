// Parte comum às duas páginas: o topo (data da última busca e, se ela estiver
// rodando, o andamento) e a leitura dos discos. Cada página define mostrar(), chamada sempre que os dados mudam.
const REPO = "hrafael2023/digamazon";
const API = "https://api.github.com/repos/" + REPO;
const $ = id => document.getElementById(id);
const DIG = 85;  // nota do Metacritic a partir desta ganha o selo "Dig!"
const real = n => n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
// Sem o "_AC_": ele recorta as bordas brancas e deixa algumas capas compridas.
const capaGrande = foto => foto.replace(/\._AC_[^.]*_\./, "._SL400_.");
let dados = null;

// A busca agora é automática, todo dia às 5h; a chave do antigo botão Dig não é mais usada.
try { localStorage.removeItem("digamazon.token"); localStorage.removeItem("digamazon.pedido"); } catch (e) {}

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

const espera = ms => new Promise(r => setTimeout(r, ms));

async function arquivo(nome) {
  // Lê direto do repositório, que é público (o Pages leva um minuto para republicar).
  const r = await fetch(`${API}/contents/${nome}?ref=main&t=${Date.now()}`,
    { headers: { "Accept": "application/vnd.github.raw+json" }, cache: "no-store" });
  if (!r.ok) throw new Error("GitHub respondeu " + r.status);
  return r.json();
}

// Barra de progresso da busca, logo abaixo do topo. O Mac conta a página a cada
// 10; entre um aviso e outro a barra anda sozinha, no ritmo medido até ali.
const SEG_POR_PAGINA = 13.5;  // ritmo esperado antes do primeiro aviso
let andamento = null, relogio = null;

function progresso(e) {
  andamento = e;
  if (!$("progresso")) $("status").insertAdjacentHTML("beforebegin",
    '<div id="progresso" class="progresso" role="progressbar" aria-label="Andamento da busca" aria-valuemin="0" aria-valuemax="100"><i></i></div>');
  if (!relogio) relogio = setInterval(desenharProgresso, 1000);
  desenharProgresso();
}

function fimProgresso() {
  clearInterval(relogio); relogio = null; andamento = null;
  $("progresso")?.remove();
}

function desenharProgresso() {
  const e = andamento;
  if (!e) return;
  const agora = Date.now(), quando = new Date(e.quando).getTime();
  const previstas = e.previstas || 75, pagina = e.pagina || 0;
  const ritmo = pagina > 0 ? Math.max(3, (quando - new Date(e.inicio).getTime()) / 1000 / pagina) : SEG_POR_PAGINA;
  let atual = pagina, texto;
  if (e.etapa === "notas") {
    atual = previstas;
    texto = "Quase lá: procurando as notas da crítica dos discos novos…";
  } else if (e.etapa === "esperando") {
    texto = `A Amazon pediu uma verificação na página ${pagina}. Esperando ela liberar (pode levar até 35 min)…`;
  } else {
    atual = Math.min(pagina + (agora - quando) / 1000 / ritmo, pagina + 10, previstas - 1);
    const faltam = Math.max(1, Math.round(((previstas - atual) * ritmo + 20) / 60));
    texto = `Página ${Math.floor(atual)} de ~${previstas} · faltam uns ${faltam} min. Pode fechar a página e voltar depois.`;
  }
  const pct = Math.round(Math.min(98, Math.max(2, atual / previstas * 95 + (e.etapa === "notas" ? 3 : 0))));
  const barra = $("progresso");
  barra.style.setProperty("--pct", pct + "%");
  barra.classList.toggle("parado", e.etapa === "esperando");
  barra.setAttribute("aria-valuenow", pct);
  status(texto);
}

// Se a página for aberta durante a busca da madrugada, mostra o andamento; se a
// última busca falhou, avisa. Sem chave, o GitHub aceita 60 leituras por hora,
// então confere a cada minuto.
async function acompanhar() {
  let viu = false;
  for (;;) {
    let e;
    try { e = await arquivo("estado.json"); } catch (err) { return; }
    if (e.estado === "buscando" && e.etapa) { viu = true; progresso(e); await espera(60000); continue; }
    fimProgresso();
    if (e.estado === "erro" && new Date(e.quando) > new Date(dados.atualizado)) status("A busca automática falhou: " + e.mensagem, true);
    else if (viu && e.estado === "ok") {
      try { exibir(await arquivo("dados.json")); } catch (err) { await carregar(); }
      status(dados.novos.length ? `Pronto: ${dados.novos.length} discos novos.` : "Pronto: nenhum disco novo desta vez.");
    } else status("");
    return;
  }
}

// Chamada pela página depois de definir mostrar().
function iniciar() { carregar().then(acompanhar).catch(e => status(e.message, true)); }
