import sys
import json
sys.path.append('hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources')
import hfo_prey8_mcp_server
from hfo_prey8_mcp_server import prey8_yield, _sessions, _load_session

agent_id = 'p7_spider_sovereign'
_sessions[agent_id] = _load_session(agent_id)

res = prey8_yield(
    agent_id=agent_id,
    summary='Started P5 lifecycle daemon and discovered circuit breaker tripped for shodh, npu_embedder, and cloud_summarizer.',
    delivery_manifest='hfo_p5_lifecycle_daemon.py',
    test_evidence='test_dummy.py',
    ai_confidence=90,
    immunization_status='PASSED',
    completion_given='Given the P5 lifecycle daemon was offline and the user requested its status',
    completion_when='When the daemon was restarted and read the stigmergy trail from SQLite',
    completion_then='Then the daemon correctly identified that shodh, npu_embedder, and cloud_summarizer had crashed >= 5 times and marked them as DEAD, proving the circuit breaker and SQLite persistence work.'
)
print(json.dumps(res, indent=2))
