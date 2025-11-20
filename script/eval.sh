
# Read API key from env; fail fast if missing
api_key="${OPENAI_API_KEY:-}"
if [[ -z "$api_key" ]]; then
  echo "OPENAI_API_KEY is not set. Export it before running: export OPENAI_API_KEY=sk-..." >&2
  exit 1
fi
model_name=gpt-4o-mini

VENV_PY="/Users/minkush/Desktop/Online-Mind2Web/venv/bin/python"

#Automatic evaluation method
modes=(
    "WebJudge_Online_Mind2Web_eval"
    "WebJudge_general_eval"
    "Autonomous_eval"
    "WebVoyager_eval"
    "AgentTrek_eval"
)

base_dir="./data/example"
for mode in "${modes[@]}"; do
    "$VENV_PY" ./src/run.py \
        --mode "$mode" \
        --model "${model_name}" \
        --trajectories_dir "$base_dir" \
        --api_key "${api_key}" \
        --output_path ${base_dir}_result \
        --num_worker 1 \
        --score_threshold 3
done
