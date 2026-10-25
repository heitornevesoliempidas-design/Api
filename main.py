from fastapi import FastAPI, HTTPException
  from playwright.async_api import async_playwright
  import requests
  import uvicorn
  import os

  app = FastAPI(title="MochiAnimes Video API")

  HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://serv01.meusdoramas.club/"}

  async def extract_mp4(tmdb, season, episode):
      # 1. Chama a API do MeusDoramas para pegar o link do Blogger
      api_url = f"https://serv01.meusdoramas.club/posts/get-video.php?episode_number={episode}&season_number={season}&tmdb={tmdb}"
      try:
          response = requests.get(api_url, headers=HEADERS, timeout=10)
          data = response.json()
      except Exception as e:
          return None, f"Erro ao conectar na API: {str(e)}"

      if not data.get("success") or not data.get("videoUrl"):
          return None, "Episódio não encontrado ou API falhou."

      blogger_url = data["videoUrl"]

      # 2. Usa Playwright Async para extrair o link do googlevideo (.mp4)
      stream_url = None
      try:
          async with async_playwright() as p:
              # Argumentos essenciais para rodar em containers (Render/Railway)
              browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
              context = await browser.new_context()
              page = await context.new_page()

              async def capture(url_str):
                  nonlocal stream_url
                  if "googlevideo.com/videoplayback" in url_str and not stream_url:
                      stream_url = url_str

              page.on("request", lambda r: capture(r.url))
              page.on("response", lambda r: capture(r.url))

              await page.goto(blogger_url, timeout=30000)

              # Simula o clique no play para disparar a requisição do vídeo
              viewport = page.viewport_size
              await page.mouse.click(viewport["width"] // 2, viewport["height"] // 2)

              # Aguarda alguns segundos para a URL do MP4 aparecer nos requests
              for _ in range(15):
                  if stream_url: break
                  await page.wait_for_timeout(1000)

              await browser.close()
      except Exception as e:
          return None, f"Erro no Playwright: {str(e)}"

      return stream_url, None

  @app.get("/")
  def read_root():
      return {"status": "Mochi API Online", "docs": "/docs"}

  @app.get("/get-video")
  async def get_video(tmdb: str, season: str, episode: str):
      """
      Endpoint para extrair o link MP4 direto.
      Exemplo: /get-video?tmdb=335194&season=1&episode=5
      """
      url, error = await extract_mp4(tmdb, season, episode)

      if error:
          raise HTTPException(status_code=404, detail=error)

      if not url:
          raise HTTPException(status_code=404, detail="Não foi possível extrair o link MP4 do vídeo.")

      return {
          "success": True,
          "tmdb": tmdb,
          "season": season,
          "episode": episode,
          "mp4_url": url
      }

  if __name__ == "__main__":
      port = int(os.environ.get("PORT", 8000))
      uvicorn.run(app, host="0.0.0.0", port=port)
