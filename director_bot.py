import os
import sys
import asyncio
import subprocess
from playwright.async_api import async_playwright
from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips

scenes = [
    {
        "id": 1,
        "text": "Quarterly S.O.X. testing is broken. It’s slow, it’s manual, and it relies on outdated sample sizes.",
        "url": "http://localhost:8000/",
        "action": "wait"
    },
    {
        "id": 2,
        "text": "Enter the Agentic A.I. Audit Suite. The world’s first autonomous, continuous compliance engine. Built to transform your data into absolute certainty.",
        "url": "http://localhost:8000/",
        "action": "scroll_down"
    },
    {
        "id": 3,
        "text": "It starts at the source. Our background Watcher Guards stream live logs from Azure A.D. and your E.R.P.s... and instantly seals every single row with an unbreakable S.H.A. 256 cryptographic hash.",
        "url": "http://localhost:8000/vault.html",
        "action": "scroll_vault"
    },
    {
        "id": 4,
        "text": "Total data isolation. The backend relies on asynchronous post-gres Q.L. with native Row-Level Security, ensuring banking-grade separation for every tenant.",
        "url": "http://localhost:8000/app.html",
        "action": "dashboard"
    },
    {
        "id": 5,
        "text": "Stop manual testing. The Command Center acts as your autonomous audit staff. With one click, it executes parameter-driven Control Evaluations and Segregation of Duties matrices across 100 percent of your data.",
        "url": "http://localhost:8000/app.html",
        "action": "scan"
    },
    {
        "id": 6,
        "text": "When the scan completes? The A.I. writes the workpaper for you. Instantly export fully compliant, Board-ready P.D.F. and Word documents with P.C.A.O.B. opinions. Upgrade your enterprise architecture today.",
        "url": "http://localhost:8000/app.html",
        "action": "scroll_docs"
    }
]

def generate_audio(text, outfile):
    print(f"Generating TTS for: {text}")
    subprocess.run(["python", "-m", "edge_tts", "-t", text, "-v", "en-US-ChristopherNeural", "--write-media", outfile], check=True)
    return AudioFileClip(outfile)

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        final_clips = []
        
        for sc in scenes:
            sid = sc['id']
            audio_path = f"C:/Users/DJ/Desktop/acap_rebuild/scene_{sid}.mp3"
            video_dir = f"C:/Users/DJ/Desktop/acap_rebuild/vid_scene_{sid}"
            os.makedirs(video_dir, exist_ok=True)
            
            # Generate Audio
            audio_clip = generate_audio(sc['text'], audio_path)
            dur = audio_clip.duration
            print(f"Scene {sid} audio duration: {dur}s")
            
            # Start Video Capture
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                record_video_dir=video_dir,
                record_video_size={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            
            print(f"Loading {sc['url']}...")
            await page.goto(sc['url'])
            
            # 1 second buffer to allow page to fully visually render before action starts
            await page.wait_for_timeout(1000) 
            
            action = sc['action']
            ms_dur = max(int(dur * 1000), 100)
            
            print(f"Executing scene action: {action} over {ms_dur}ms")
            try:
                if action == "wait" or action == "dashboard":
                    await page.wait_for_timeout(ms_dur)
                    
                elif action == "scroll_down":
                    steps = 30
                    delay = ms_dur / steps
                    for _ in range(steps):
                        await page.mouse.wheel(0, 30)
                        await page.wait_for_timeout(delay)
                        
                elif action == "scroll_vault":
                    steps = 40
                    delay = ms_dur / steps
                    for _ in range(steps):
                        await page.mouse.wheel(0, 45)
                        await page.wait_for_timeout(delay)
                        
                elif action == "scan":
                    # Scroll actively through the command center table
                    steps = 30
                    delay = ms_dur / steps
                    for _ in range(steps):
                        await page.mouse.wheel(0, 35)
                        await page.wait_for_timeout(delay)
                        
                elif action == "scroll_docs":
                    # Instant scroll to module 3 at bottom
                    await page.mouse.wheel(0, 2000)
                    await page.wait_for_timeout(500)
                    await page.mouse.wheel(0, 500)
                    await page.wait_for_timeout(ms_dur - 500)
                    
                else:
                    await page.wait_for_timeout(ms_dur)
            except Exception as e:
                print(f"Action error: {e}")
                
            await page.wait_for_timeout(1000) # post buffer
            await context.close() # Closes page and writes video
            
            files = [f for f in os.listdir(video_dir) if f.endswith('.webm')]
            if not files:
                print(f"Warning: No video found for scene {sid}")
                continue
                
            webm_path = os.path.join(video_dir, files[0])
            print(f"Processing WEBM mapping: {webm_path}")
            
            vid_clip = VideoFileClip(webm_path)
            start_t = 1.0
            end_t = min(1.0 + dur, vid_clip.duration - 0.1)
            
            # Slice it exact
            try:
                sliced = vid_clip.subclipped(start_t, end_t)
            except AttributeError:
                sliced = vid_clip.subclip(start_t, end_t)
                
            # Attach audio
            try:
                final_scene = sliced.with_audio(audio_clip)
            except AttributeError:
                final_scene = sliced.set_audio(audio_clip)
                
            final_clips.append(final_scene)
            
        print("Concatenating all scenes into Final Marketing Video...")
        final_video = concatenate_videoclips(final_clips)
        
        out_path = "C:/Users/DJ/Desktop/acap_rebuild/Ultimate_Automation_Showcase.mp4"
        final_video.write_videofile(out_path, codec="libx264", audio_codec="aac", fps=30, logger=None)
        
        await browser.close()
        print(f"Successfully minted final video: {out_path}")

if __name__ == "__main__":
    asyncio.run(run())
