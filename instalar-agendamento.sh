#!/bin/zsh
# Deixa o Mac conferindo a cada 2 minutos se o botão Pesquisar foi tocado
# (LaunchAgent do macOS). Só funciona com o Mac ligado e acordado; um pedido
# feito com ele dormindo é atendido quando ele acordar.
# Para remover: ./instalar-agendamento.sh --remover
set -e
PASTA="${0:A:h}"
ROTULO="org.projetoninho.digamazon"
PLIST="$HOME/Library/LaunchAgents/$ROTULO.plist"

launchctl bootout "gui/$(id -u)/$ROTULO" 2>/dev/null || true
if [[ "$1" == "--remover" ]]; then
  rm -f "$PLIST"; echo "Agendamento removido."; exit 0
fi

mkdir -p "$PASTA/logs" "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$ROTULO</string>
  <key>ProgramArguments</key><array>
    <string>$(command -v python3)</string><string>$PASTA/atender.py</string>
  </array>
  <key>WorkingDirectory</key><string>$PASTA</string>
  <key>StartInterval</key><integer>120</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$PASTA/logs/atender.log</string>
  <key>StandardErrorPath</key><string>$PASTA/logs/atender.log</string>
</dict></plist>
EOF
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Pronto: o Mac confere os pedidos a cada 2 minutos (log em $PASTA/logs/atender.log)."
