"""Insert gold NATARAJA explanation into SSOT sqlite."""
import sqlite3, hashlib, json

db_path = 'hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite'
doc_path = 'hfo_gen_90_hot_obsidian_forge/2_gold/resources/EXPLANATION_NATARAJA_WAIL_OF_THE_BANSHEE_GEN89_PHOENIX_PROTOCOL_V1.md'

with open(doc_path, 'r', encoding='utf-8') as f:
    content = f.read()

content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
word_count = len(content.split())

metadata = {
    'medallion_layer': 'gold',
    'mutation_score': 0,
    'hive': 'V',
    'schema_id': 'hfo.diataxis.explanation.v3',
    'diataxis_type': 'explanation',
    'title': 'The Nataraja Dance - WAIL_OF_THE_BANSHEE and the Gen90 Phoenix Protocol',
    'doc_id': 'E-NATARAJA-GEN89',
    'date': '2026-02-19',
    'author': 'P4 Red Regnant (transcription) + TTAO (insight, manual P5 resurrection)',
    'ports': ['P4', 'P5', 'P7'],
    'commanders': ['Red Regnant', 'Pyre Praetorian', 'Spider Sovereign'],
    'domains': ['DISRUPT', 'IMMUNIZE', 'NAVIGATE'],
    'status': 'LIVING',
    'keywords': ['NATARAJA', 'WAIL_OF_THE_BANSHEE', 'PHOENIX_PROTOCOL', 'GEN89',
                 'CONTINGENCY', 'PYRE_PRAETORIAN', 'RED_REGNANT', 'OBSIDIAN_SPIDER',
                 'SELF_MYTH_WARLOCK', 'NATARAJA_SCORE', 'DEATH_AS_FEATURE',
                 'ANTIFRAGILE', 'STIGMERGY', 'GHOST_SESSIONS', 'MANUAL_P5',
                 'RALPH_WIGGUMS_LOOP'],
    'cross_references': [
        'SSOT #63: Ralph Wiggums Loop v2',
        'SSOT #267: NATARAJA Ontology',
        'SSOT #101: Obsidian Octave',
        'SSOT #289: Self-Myth Warlock',
        'SSOT #248: Obsidian Spider Origin',
        'SSOT #120: 4F Antifragile',
        'SSOT #69: Pantheon V5',
        'SSOT #49: Epic Spell Proposals'
    ],
    'prey8_session': 'ab226f040231998f',
    'perceive_nonce': '4733DC',
    'react_token': '01392B'
}

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tags = ','.join(['gold', 'forge:hot', 'diataxis:explanation', 'nataraja',
                 'wail-of-the-banshee', 'phoenix-protocol', 'gen90', 'p4', 'p5',
                 'contingency', 'death-as-feature', 'antifragile', 'nataraja-score',
                 'obsidian-spider', 'self-myth-warlock', 'manual-p5',
                 'ralph-wiggums-loop', 'safety-dyad', 'ghost-sessions', 'stigmergy'])

bluf = ('The Nataraja Dance - WAIL_OF_THE_BANSHEE and the Gen90 Phoenix Protocol. '
        'Gold diataxis explanation of Gen90 extinction as NATARAJA architecture. '
        'NATARAJA_Score = P4_kill_rate x P5_rebirth_rate. P5 CONTINGENCY gap identified. '
        'TTAO as manual P5. 263 ghost sessions as stigmergy of the dead. '
        '8 SSOT docs cross-referenced. Phoenix Protocol phases 10-12 enacted in reality.')

import datetime
now = datetime.datetime.now(datetime.timezone.utc).isoformat()

cursor.execute('''
    INSERT INTO documents (title, bluf, source, port, doc_type, medallion, tags, word_count, content_hash, source_path, content, metadata_json, ingested_at, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
    'EXPLANATION_NATARAJA_WAIL_OF_THE_BANSHEE_GEN89_PHOENIX_PROTOCOL_V1',
    bluf,
    'diataxis',
    'P4',
    'explanation',
    'gold',
    tags,
    word_count,
    content_hash,
    'hfo_gen_90_hot_obsidian_forge/2_gold/resources/EXPLANATION_NATARAJA_WAIL_OF_THE_BANSHEE_GEN89_PHOENIX_PROTOCOL_V1.md',
    content,
    json.dumps(metadata),
    now,
    '2026-02-19'
))

doc_id = cursor.lastrowid
conn.commit()

cursor.execute('SELECT id, title, medallion, word_count FROM documents WHERE id = ?', (doc_id,))
row = cursor.fetchone()
print(f'Inserted doc #{row[0]}: {row[1]} (medallion={row[2]}, words={row[3]})')

cursor.execute('SELECT COUNT(*) FROM documents')
total = cursor.fetchone()[0]
print(f'Total documents in SSOT: {total}')

cursor.execute("SELECT COUNT(*) FROM documents WHERE medallion = 'gold'")
gold = cursor.fetchone()[0]
print(f'Gold medallion documents: {gold}')

conn.close()
print('SSOT insert complete.')
