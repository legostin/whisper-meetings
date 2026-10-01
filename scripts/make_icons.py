"""Render our own monochrome waveform mark. Requires Pillow for development only."""
from pathlib import Path
from PIL import Image, ImageDraw

root=Path(__file__).resolve().parents[1]/'plugins/whisper-meetings/assets'
root.mkdir(exist_ok=True)
for dark,background,foreground in ((False,'#202020','#ffffff'),(True,'#eeeeee','#171717')):
    image=Image.new('RGBA',(1024,1024),(0,0,0,0));draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((48,48,976,976),radius=268,fill=background)
    for x,height in ((276,120),(394,320),(512,500),(630,300),(748,100)):
        draw.rounded_rectangle((x-28,512-height//2,x+28,512+height//2),radius=28,fill=foreground)
    suffix='-dark' if dark else ''
    image.resize((256,256),Image.Resampling.LANCZOS).save(root/f'icon{suffix}.png')
    image.resize((512,512),Image.Resampling.LANCZOS).save(root/f'logo{suffix}.png')
