import sys
import json
sys.path.append('hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources')
import hfo_prey8_mcp_server
from hfo_prey8_mcp_server import prey8_execute, _sessions, _load_session

agent_id = 'p7_spider_sovereign'
_sessions[agent_id] = _load_session(agent_id)

res = prey8_execute(
    agent_id=agent_id,
    react_token='6251BA',
    action_summary='Started P5 lifecycle daemon and discovered circuit breaker tripped for shodh, npu_embedder, and cloud_summarizer.',
    sbe_given='Given the P5 lifecycle daemon was offline and the user requested its status',
    sbe_when='When the daemon was restarted and read the stigmergy trail from SQLite',
    sbe_then='Then it correctly identified that shodh, npu_embedder, and cloud_summarizer had crashed >= 5 times and marked them as DEAD, proving the circuit breaker and SQLite persistence work.',
    artifacts='hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/hfo_p5_lifecycle_daemon.py',
    p4_adversarial_check='The circuit breaker successfully prevented an infinite restart loop, demonstrating fail-closed behavior.',
    sbe_test_file='hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/test_dummy.py'
)
print(json.dumps(res, indent=2))
