---
layout: page
title: Updates
lang: en
description: News and progress on the TS Pico project.
---

<ul class="updates-list">
{% for post in site.posts %}
  <li>
    <h2><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h2>
    <time datetime="{{ post.date | date_to_xmlschema }}">{{ post.date | date: "%B %-d, %Y" }}</time>
    <div class="excerpt">{{ post.excerpt | strip_html | strip_newlines | truncatewords: 40 }}</div>
  </li>
{% endfor %}
</ul>
