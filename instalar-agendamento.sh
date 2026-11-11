#!/bin/zsh
# Deixa o Mac conferindo a cada 2 minutos se é hora da busca automática do dia
# (LaunchAgent do macOS). Só funciona com o Mac ligado e acordado; para ele
# acordar sozinho às 5h, veja o README.
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
echo "Pronto: o Mac busca os discos todo dia a partir das 5h (log em $PASTA/logs/atender.log)."
