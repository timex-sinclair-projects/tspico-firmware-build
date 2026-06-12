---
layout: home
title: TS Pico Interface
lang: en
description: >-
  The TS Pico is a modern expansion platform for the Timex/Sinclair 2068 —
  ultra-fast load and save from an SD card, powered by a Raspberry Pi Pico.
---
<section class="hero">
  <div class="wrap">
    <h1>TS Pico Interface</h1>
    <p class="lead">A modern expansion platform for the Timex/Sinclair&nbsp;2068.</p>
    <div class="btn-row">
      <a class="btn btn-buy" href="{{ site.buy_tspico }}">Buy a TS&nbsp;Pico</a>
      <a class="btn" href="{{ site.updater_url | relative_url }}">Open the Web Updater</a>
    </div>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="video-embed">
      <iframe src="https://www.youtube-nocookie.com/embed/EzBxEjLAhe8" title="TS Pico Interface Introduction" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>
    </div>

    <h2>What is the TS Pico?</h2>

    <p>The TS Pico is a modern expansion platform for the Timex/Sinclair 2068. It comes with software that lets you load and save from/to digital media. It plugs into the back of your TS 2068, works with your tape recorder, other digital devices, and gives you ultra-fast load and save.</p>

    <p>At its heart, it’s a <a href="https://www.raspberrypi.com/documentation/microcontrollers/raspberry-pi-pico.html">Raspberry Pi Pico</a>, 512K Flash ROM, 512K RAM, an SD card slot and supporting circuitry that connects to your Timex/Sinclair 2068.</p>

    <figure><img src="{{ '/assets/img/ts-pico-cover.png' | relative_url }}" alt="The TS Pico board"></figure>

    <p>It can be a lot of things because you can program the Pico in MicroPython. Talking to it from BASIC or machine language is as simple as an OUT/IN statements.</p>

    <p>The TS Pico will be supplied with a special image on the Flash ROM that enhances the TS 2068 BASIC with new commands that will let you load, run and save existing and new software.</p>

    <figure><img src="{{ '/assets/img/ts-pico-back-of-2068.png' | relative_url }}" alt="The TS Pico connected to the back of a TS 2068"></figure>

    <div class="btn-row">
      <a class="btn btn-buy" href="{{ site.buy_tspico }}">Buy Now</a>
    </div>
  </div>
</section>

<section class="section alt">
  <div class="wrap">
    <div class="promo">
      <div>
        <h2>Interested in the PicoVideo for your TS 2068?</h2>
        <p>The PicoVideo is a Raspberry Pi Pico-based solution that gives your TS 2068 crystal clear VGA output.</p>
        <p><a class="btn btn-buy" href="{{ site.buy_picovideo }}">Buy Now</a></p>
      </div>
      <img src="{{ '/assets/img/picovideo.png' | relative_url }}" alt="PicoVideo VGA output on a monitor">
    </div>
  </div>
</section>
