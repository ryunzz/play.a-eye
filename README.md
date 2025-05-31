# Welcome to play.a-eye
Team: Ryan Ni, May Hong, Matthew Lu, Keerthi Nalabotu, Aryn Ni

--

## Inspiration
We've always wanted our own Meta RayBan glasses to play around with, but their $300 price tag was far too expensive for us. So what did we do? We tried our best to make our own version that would better fit our budget.

## What it does
play.a-eye can be described as smart glasses with augmented reality features that allows users to play an assortment of fun games we've designed as well as live audio transcription and translation for non-English speakers. We've also implemented generative AI to allow for unlimited knowledge for our users via our "Hey, Sentient" feature.

## How we built it
The system uses an Arduino Nano as the central controller, connected to an HC-05 Bluetooth module for wireless communication with a computer. Spoken English is captured through a microphone, transcribed and translated using AI via the Google Speech Detect API and OpenAI API, and then sent back to the glasses in real time. The translated text is displayed on a small OLED screen mounted inside the glasses that is reflected by a 90* mirror onto an acrylic panel allowing users to not obstruct their vision.

## Challenges we ran into
Our biggest challenge was designing the hardware and connecting it to our software. We had to perform research on how light refraction and magnifying glasses work. Since none of our members had experience with hardware originally, this was a really big learning moment for all of us. Then, we had to research parts, buy them, assemble them, and then configure them. This involved figuring out how to get parts cut correctly, assembled. 

## Accomplishments that we're proud of
We’re proud that we have a fully functional play.a-eye glasses that successfully allows us to play games and translate/transcribe live speech with minimal latency, using generative AI in a practical, wearable format.

## How to run
You can run our software by first installing all the necessary python dependencies and uploading your API keys. Then, you just simply run "python mic_to_text.py". Unfortunately, since most of our project is hardware, you can't recreate that at home.

## What's next for play.a-eye
We will eventually expand our collection of possible games in the future and possibly improving on our prototyped casing!
