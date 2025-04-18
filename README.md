## Inspiration
Our entire team comes from immigrant families, where our parents have faced challenges with their lack of native English speaking skill. In our personal experiences, we have encountered many workers in America with barely any English skill. We strive to take down this language barrier to enable people of all backgrounds hold a job in America.

## What it does
LinguaLens is a wearable augmented reality device designed to assist non-English-speaking workers in understanding spoken English in real time. It is primarily intended for immigrants in blue-collar environments, such as house cleaners, who may struggle with language barriers at work. It utilizes artificial intelligence to recognize speech and translate phrases.

## How we built it
The system uses an Arduino Nano as the central controller, connected to an HC-05 Bluetooth module for wireless communication with a computer. Spoken English is captured through a microphone, transcribed and translated using AI via the OpenAI API, and then sent back to the glasses in real time. The translated text is displayed on a small OLED screen mounted inside the glasses.

To make the text visible to the wearer, a mirror and magnifying lens setup projects the display into the user’s line of sight without obstructing normal vision. All components are housed within a 3D printed shell designed to be lightweight and wearable throughout a workday.

## How to run

