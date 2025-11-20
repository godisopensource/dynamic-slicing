#!/usr/bin/env fish
# Startup script for NexSlice dynamic slicing controller
# Deploys 5G core if needed, starts Flask controller, Prometheus and shows status

set NAMESPACE "nexslice"

echo "═══════════════════════════════════════════════"
echo "  NexSlice — Dynamic 5G Slicing Controller"
echo "═══════════════════════════════════════════════"
echo ""

# Check prerequisites
echo "[1/5] Checking prerequisites..."

if not command -v kubectl &> /dev/null
    echo "❌ ERROR: kubectl not found. Please install kubectl."
    exit 1
end

if not command -v helm &> /dev/null
    echo "❌ ERROR: helm not found. Please install helm."
    exit 1
end

if not command -v python3 &> /dev/null
    echo "❌ ERROR: python3 not found. Please install Python 3.9+."
    exit 1
end

echo "✅ All prerequisites found (kubectl, helm, python3)"
echo ""

# Check if 5G core is deployed
echo "[2/5] Checking 5G core network deployment..."

set CORE_PODS (kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=oai-amf --no-headers 2>/dev/null | wc -l)

if test $CORE_PODS -eq 0
    echo "⚠️  5G core network not found in namespace '$NAMESPACE'"
    echo "    Would you like to deploy it now? (requires internet and ~5 minutes)"
    read -P "    Deploy 5G core? [y/N]: " deploy_core
    
    if test "$deploy_core" = "y" -o "$deploy_core" = "Y"
        echo "    Deploying 5G core network..."
        ./scripts/deploy_5g_core.sh
        if test $status -ne 0
            echo "❌ Failed to deploy 5G core. Check logs above."
            exit 1
        end
        echo "✅ 5G core deployment initiated. Waiting for pods to be ready..."
        kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=oai-amf -n $NAMESPACE --timeout=300s
    else
        echo "    Skipping 5G core deployment. Note: UE/UPF pods will not work without it."
    end
else
    echo "✅ 5G core network found ($CORE_PODS AMF pods running)"
end
echo ""

# Setup Python virtualenv
echo "[3/5] Setting up Python environment..."

if not test -d .venv
    echo "    Creating virtualenv..."
    python3 -m venv .venv
end

if test -f .venv/bin/activate.fish
    source .venv/bin/activate.fish
else if test -f .venv/bin/activate
    source .venv/bin/activate
end

if not pip show flask > /dev/null 2>&1
    echo "    Installing Python dependencies..."
    pip install -q -r requirements.txt
end

echo "✅ Python environment ready"
echo ""

# Start Prometheus (if not running)
echo "[4/5] Starting monitoring stack..."

if not pgrep -f 'prometheus.*prometheus.yml' > /dev/null
    echo "    Starting Prometheus..."
    prometheus --config.file=prometheus.yml > /tmp/prometheus.log 2>&1 &
    echo $! > /tmp/prometheus.pid
    sleep 2
    if pgrep -f 'prometheus.*prometheus.yml' > /dev/null
        echo "✅ Prometheus started (http://localhost:9090)"
    else
        echo "⚠️  Prometheus failed to start (check /tmp/prometheus.log)"
    end
else
    echo "✅ Prometheus already running"
end

# Optional: Start Grafana
if command -v grafana-server &> /dev/null
    if not pgrep -f 'grafana-server' > /dev/null
        echo "    Starting Grafana..."
        grafana-server --homepath /usr/share/grafana > /tmp/grafana.log 2>&1 &
        echo $! > /tmp/grafana.pid
        sleep 2
        if pgrep -f 'grafana-server' > /dev/null
            echo "✅ Grafana started (http://localhost:3000, login: admin/admin)"
        else
            echo "⚠️  Grafana failed to start (check /tmp/grafana.log)"
        end
    else
        echo "✅ Grafana already running"
    end
else
    echo "ℹ️  Grafana not found (optional, skipping)"
end
echo ""

# Start Flask controller
echo "[5/5] Starting Flask controller..."

if pgrep -f 'python -m src.main' > /dev/null
    echo "⚠️  Flask controller already running. Stop it first with: pkill -f 'python -m src.main'"
    exit 1
end

set -gx DEMO_MODE 0
echo "    Starting Flask in cluster mode (DEMO_MODE=0)..."
echo "    Logs: /tmp/nexslice_flask.log"

nohup ./.venv/bin/python -m src.main > /tmp/nexslice_flask.log 2>&1 &
echo $! > /tmp/nexslice_flask.pid
sleep 2

if pgrep -f 'python -m src.main' > /dev/null
    echo "✅ Flask controller started"
else
    echo "❌ Flask controller failed to start"
    echo "    Check logs: tail -f /tmp/nexslice_flask.log"
    exit 1
end

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ NexSlice is running!"
echo "═══════════════════════════════════════════════"
echo ""
echo "📡 Web Interface:  http://localhost:5000"
echo "📊 Prometheus:     http://localhost:9090"
if command -v grafana-server &> /dev/null
    echo "📈 Grafana:        http://localhost:3000"
end
echo ""
echo "🔧 Useful commands:"
echo "   • kubectl get pods -n $NAMESPACE"
echo "   • tail -f /tmp/nexslice_flask.log"
echo "   • curl http://localhost:5000/metrics"
echo ""
echo "🛑 To stop all services:"
echo "   pkill -f 'python -m src.main'"
echo "   pkill -f 'prometheus.*prometheus.yml'"
if command -v grafana-server &> /dev/null
    echo "   pkill -f 'grafana-server'"
end
echo ""
