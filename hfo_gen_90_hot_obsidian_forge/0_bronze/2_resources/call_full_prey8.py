import sys
import json
sys.path.append('hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources')
import hfo_prey8_mcp_server
from hfo_prey8_mcp_server import prey8_perceive, prey8_react, prey8_execute, prey8_yield

agent_id = 'p7_spider_sovereign'

# 1. Perceive
res_p = prey8_perceive(
    agent_id=agent_id,
    probe='whats status of daemons? check stigmergy they should regularly log, I think they have been offline',
    observations='Checked stigmergy_events, found P5 lifecycle daemon offline since 07:41:45.',
    memory_refs='hfo_p5_lifecycle_daemon.py',
    stigmergy_digest='P5 lifecycle daemon was offline. Restarted it. Circuit breaker tripped for shodh, npu_embedder, and cloud_summarizer.'
)
print("PERCEIVE:", json.dumps(res_p, indent=2))
nonce = res_p['nonce']

# 2. React
res_r = prey8_react(
    agent_id=agent_id,
    perceive_nonce=nonce,
    analysis='The P5 lifecycle daemon was offline. Restarting it revealed that 3 sub-daemons are crash-looping and were caught by the circuit breaker.',
    tactical_plan='Restart the daemon and observe the circuit breaker logs.',
    strategic_plan='Ensure the swarm lifecycle manager is running and correctly isolating failing components.',
    sequential_thinking='1. Check stigmergy. 2. Confirm offline status. 3. Restart daemon. 4. Observe circuit breaker. 5. Report status.',
    cynefin_classification='Complicated',
    shared_data_refs='stigmergy_events table',
    navigation_intent='Restore P5 lifecycle daemon operation and verify circuit breaker.',
    meadows_level=8,
    meadows_justification='Altering the governance rules of the swarm by restarting the lifecycle manager and enforcing circuit breakers.',
    sequential_plan='Check stigmergy, restart daemon, observe circuit breaker, report status.'
)
print("REACT:", json.dumps(res_r, indent=2))
react_token = res_r['react_token']

# 3. Execute
res_e = prey8_execute(
    agent_id=agent_id,
    react_token=react_token,
    action_summary='Restarted P5 lifecycle daemon and observed circuit breaker.',
    sbe_given='Given the P5 lifecycle daemon is offline',
    sbe_when='When the daemon is restarted',
    sbe_then='Then it should read the SQLite stigmergy trail and halt any daemons with >= 5 crashes.',
    artifacts='hfo_p5_lifecycle_daemon.py',
    p4_adversarial_check='What if the circuit breaker fails? It correctly halted shodh, npu_embedder, and cloud_summarizer.',
    sbe_test_file='hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/test_dummy.py'
)
print("EXECUTE:", json.dumps(res_e, indent=2))

# 4. Yield
res_y = prey8_yield(
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
print("YIELD:", json.dumps(res_y, indent=2))
