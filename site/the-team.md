---
layout: page
title: The Team
lang: en
description: The people behind the TS Pico — Ricardo, Gustavo, Jeff, Tim and David.
---

## Ricardo Calcagno

<img class="portrait" src="{{ '/assets/img/ricardo.jpg' | relative_url }}" alt="Ricardo Calcagno">

I am a systems engineer, former teacher at National Technological University and presently a businessman who lives in [Resistencia](https://en.wikipedia.org/wiki/Resistencia,_Chaco), a city north of Argentina.

My first computer was a Timex Sinclair 2068, obtained in 1984. Living outside the big cities in Argentina, choices were limited in my town: the TI-99/4A and the much more affordable TS. I always enjoyed the forward approach of the TS: the keystrokes with the tokens that would save many typos, the relatively simple architecture, the slick, beautiful and futuristic hardware, the extensive software library in cassette I could get in my city, the many type-in programs for Spectrum that you could use right at start.

I left my computer somewhere in my parent’s house when I finished high school and eventually lost it. Later, in the late 1990s, I got one cheap online. Stored it and forgot all about it.

During pandemic, with all the time of the world and trying not to lose my mind, I dusted off my TS and tried to play some old games, but what bugged me was the lack of a proper native storage solution, like the DivIDE/DivMMC for the Spectrum. Digging online, found [Dr. Beep’s PC-ZX project](https://trastero.speccy.org/cosas/JL/DrBeep/PC-ZX.html).

I wondered if that would be possible today, but using a Raspberry Pico, the Pico’s PIOs and Python instead of a PC, the parallel port and Turbo Pascal. This, my first such project, worked and I shared my progress with the community. It is the core of the current TS-Pico project, enhanced with the invaluable contributions of David, Gustavo, Jeff and Tim (in alphabetical order). Today, I am responsible for the main Python programming, including the State Machines that control the I/O to/from the TS.

The TS-Pico has grown to be a much better and complete solution, but keeping it’s essential open concept, that allows you, the user, to interact and “play” with the hardware/software on your loved TS2068 in ways I am sure you’ll find amazing, creating your own routines and adding functionalities, and sharing them with your fellow users.

## Gustavo Pane

<img class="portrait" src="{{ '/assets/img/gustavo.jpg' | relative_url }}" alt="Gustavo Pane">

I have been fortunate to be able to use Sinclair computers since the early 1980s. My first computer was a Timex Sinclair 2068, obtained in the year 1984, when my father gave it to me to use it in my electronics studies, just as I was finishing high school.

From that moment on, the learning curve became exponential. I started programming in BASIC, using it to solve mathematical equations, electronic applications, calculations of transistorized circuits, and 2D and 3D graphics.

I always preferred to focus on low-level programming, using machine language, particularly for the Z80 microprocessor. Almost all of my routines and programs developed on the TS-2068 were written using Zeus Assembler.

At that time, I was dedicated to the programming of BIOS and professional applications for CP/M and MP/M 80 and I found in the TS-2068 a great integrated and easy-to-use platform to develop systems with microprocessors.

I soon realized that I needed a storage method for saving and loading programs and data that would be faster and more reliable than the original cassette system. I decided to create an interface to connect the TS-2068 with a more powerful computer running CP/M so I could use a 40MB hard drive to store my programs.

I used my knowledge of electronics and programming, modifying the use of the original SAVE/LOAD commands, but simultaneously keeping the cassette system, because my entire library was saved on tape.

Today, 40 years after the launch of the TS-2068, I found it useful to adapt my CP/M storage routines to the latest, most advanced TS-Pico interface available today. In addition to the original version, which only supported SAVE/LOAD/VERIFY/MERGE, I have included the COPY/LPRINT/LLIST commands so that they can be handled by the TS-Pico. You are able to save to text files or image files, intended for the TS-2040 printer, on the SD cards.

I am very proud to be part of this group of four people who are part of this new project, and I want to publicly thank the other members of the team, who have helped make it possible for my program written 40 years ago to be part of this storage solution for the TS-2068.

## Jeff Burrell

Jeff’s first computer was a Sinclair ZX-81 that was purchased while he was in the US Air Force stationed in the UK. At that time, he was a technician working on advanced microwave satellite communications equipment and had access to a Hewlett-Packard minicomputer with a FORTRAN compiler.

This, along with his programming experience in college, led him to purchase the ZX-81 when he saw it advertised in a British electronics magazine. Over the five or so years that he used that computer, he learned to program in BASIC and hand-assembled machine code and to use the features and limitations of the “little black door-stop” to the fullest.

While stationed at Offutt AFB, a co-worker that was moving up to a CP/M based computer from his TS-2068. When he saw the 2068, he knew he wanted it. He had been impressed by the functionality that Clive Sinclair had managed to squeeze into the ZX-81 and, from examining the documentation of the TS-2068, he saw that this was a machine with much promise. He bought the machine and started programming right away and found, as expected, that there was much to like about the 2068.

Jeff has brought his professional experience in designing printed circuit boards to the project, adapting and improving on Ricardo’s original design.

## Tim H

Tim H is, unlike the others on the team, a relative newcomer to the Timex Sinclair 2068. Living in New Zealand, Tim’s earliest microcomputer experiences included the Sinclair models: the ZX81 and ZX Spectrum.

Within the past few years, Tim acquired a TS 2068 and became active in the international TS community, helping preserve and improve hardware designed by TS enthusiasts in the past, including a video capture board developed by TS user group members in the late 1980s.

Tim joined the team early, offering his software and hardware design support to the project.

## David Anderson

<img class="portrait" src="{{ '/assets/img/david.png' | relative_url }}" alt="David Anderson (on the right)">

I am the person behind [timexsinclair.com](https://timexsinclair.com) and I host regular Zoom meetings for fellow TS enthusiasts.

My first home computer was the Timex Sinclair 1000, which I spent many hours learning on and programming. Playing with my 1000 all night (an easy thing to do as a young teenager) was pretty common.

My early experiences with many computers, from home micros to mainframes, led to a career in IT and eventually to developing and managing websites.

Despite owning multiple, different systems, my favorites have always been the Timex Sinclair 1000 and 2068. I have a 2068 on his desk that sees action several times a week.

When Ricardo and Gustavo reached out to me about the TS Pico, I immediately recommended Tim H as a potential team member. Not long after, I suggested inviting Jeff, who was working on a similar project, to coordinate efforts and ensure the two projects would work together. Jeff was quickly pulled into the TS Pico project as well.

In this project, I have facilitated weekly team meetings and helped keep the scope focused on the goal of launching near the 40th anniversary of the TS 2068. I’m working on the user guide and will eventually make the TS Pico available through my site, [andertone.com](https://www.andertone.com).
