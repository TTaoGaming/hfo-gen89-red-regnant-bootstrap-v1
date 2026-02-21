import os
import requests

def download_file(url, dest_path):
    print(f"Downloading {url} to {dest_path}")
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        with open(dest_path, 'wb') as out_file:
            out_file.write(response.content)
    except Exception as e:
        print(f"Failed to download {url}: {e}")

def setup_sculptgl():
    base_dir = r"C:\hfoDev\hfo_gen_89_hot_obsidian_forge\1_silver\projects\omega_v13_microkernel\exemplars\simple_canvas"
    os.makedirs(base_dir, exist_ok=True)
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple Canvas Exemplar</title>
    <style>
        body { margin: 0; padding: 0; overflow: hidden; background: #f0f0f0; }
        canvas { display: block; background: white; box-shadow: 0 0 10px rgba(0,0,0,0.1); margin: 20px auto; }
    </style>
</head>
<body>
    <canvas id="drawCanvas" width="800" height="600"></canvas>
    <script>
        const canvas = document.getElementById('drawCanvas');
        const ctx = canvas.getContext('2d');
        let isDrawing = false;

        canvas.addEventListener('pointerdown', (e) => {
            isDrawing = true;
            ctx.beginPath();
            ctx.moveTo(e.offsetX, e.offsetY);
        });

        canvas.addEventListener('pointermove', (e) => {
            if (isDrawing) {
                ctx.lineTo(e.offsetX, e.offsetY);
                ctx.stroke();
            }
        });

        canvas.addEventListener('pointerup', () => {
            isDrawing = false;
        });
        
        canvas.addEventListener('pointercancel', () => {
            isDrawing = false;
        });
    </script>
</body>
</html>"""
    with open(os.path.join(base_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Created simple canvas exemplar at {base_dir}")

def setup_tldraw():
    base_dir = r"C:\hfoDev\hfo_gen_89_hot_obsidian_forge\1_silver\projects\omega_v13_microkernel\exemplars\tldraw"
    os.makedirs(base_dir, exist_ok=True)
    
    # For tldraw, we can create a simple HTML file that uses the unpkg CDN
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>tldraw Exemplar</title>
    <style>
        body { margin: 0; padding: 0; overflow: hidden; }
        #tldraw-container { width: 100vw; height: 100vh; }
    </style>
    <!-- React and ReactDOM -->
    <script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
    <!-- tldraw -->
    <link rel="stylesheet" href="https://unpkg.com/@tldraw/tldraw@2.0.0/tldraw.css" />
    <script src="https://unpkg.com/@tldraw/tldraw@2.0.0/tldraw.umd.js"></script>
</head>
<body>
    <div id="tldraw-container"></div>
    <script>
        const { Tldraw } = window.tldraw;
        const root = ReactDOM.createRoot(document.getElementById('tldraw-container'));
        root.render(React.createElement(Tldraw));
    </script>
</body>
</html>"""
    with open(os.path.join(base_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Created tldraw exemplar at {base_dir}")

if __name__ == "__main__":
    setup_sculptgl()
    setup_tldraw()
