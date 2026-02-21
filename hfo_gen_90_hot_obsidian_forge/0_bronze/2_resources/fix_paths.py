import os
import glob

for filepath in glob.glob('hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/*.py'):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = content.replace('Gen89', 'Gen90')
        content = content.replace('gen89', 'gen90')
        content = content.replace('Gen88', 'Gen89')
        content = content.replace('gen88', 'gen89')
        content = content.replace('hfo_gen_89_hot_obsidian_forge', 'hfo_gen_90_hot_obsidian_forge')
        content = content.replace('\"2_gold\" / \"resources\"', '\"2_gold\" / \"2_resources\"')
        content = content.replace('\"0_bronze\" / \"resources\"', '\"0_bronze\" / \"2_resources\"')
        content = content.replace('\"1_silver\" / \"resources\"', '\"1_silver\" / \"2_resources\"')
        content = content.replace('\"3_hyper_fractal_obsidian\" / \"resources\"', '\"3_hyper_fractal_obsidian\" / \"2_resources\"')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"Skipping {filepath}: {e}")
