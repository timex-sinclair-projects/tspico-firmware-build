-- pandoc filter for the PDF manual (make.sh):
--
-- 1. Program listings as the 2068 lists them: a code block whose lines all
--    start with a line number is a listing. Each number takes the first four
--    columns, right-aligned, then a space; every line is then cut at exactly
--    32 characters, splitting words and keywords as the 2068's screen and the
--    2040/2050 printouts do. The block gets class "listing" (print.css draws it
--    32 columns wide and doesn't wrap it again).
--
-- 2. Lead-ins that would be stranded at the foot of a page: a paragraph that
--    ends with a colon, or is a bold lead-in on its own ("**The jumpers.**"),
--    goes into one <div class="keep"> with the block after it, which print.css
--    won't break (Chrome ignores break-after: avoid). That is free for code
--    and pictures, which never break anyway; a list or table only joins its
--    lead-in when it's short, so a long one can still run over a page.

local WIDTH = 32

local function utf8_chars(s)
  local t = {}
  for _, c in utf8.codes(s) do t[#t + 1] = utf8.char(c) end
  return t
end

local function listing(text)
  local out = {}
  for line in (text .. "\n"):gmatch("(.-)\n") do
    local num, rest = line:match("^(%d+) (.*)$")
    if num then line = string.rep(" ", 4 - #num) .. num .. " " .. rest end
    local cs = utf8_chars(line)
    if #cs == 0 then out[#out + 1] = "" end
    for i = 1, #cs, WIDTH do
      out[#out + 1] = table.concat(cs, "", i, math.min(i + WIDTH - 1, #cs))
    end
  end
  return table.concat(out, "\n")
end

local function is_listing(text)
  local any = false
  for line in (text .. "\n"):gmatch("(.-)\n") do
    if line:match("%S") then
      if not line:match("^%d+ ") then return false end
      any = true
    end
  end
  return any
end

function CodeBlock(cb)
  if #cb.classes == 0 or cb.classes[1] == "basic" then
    if is_listing(cb.text) then
      cb.text = listing(cb.text)
      cb.classes = { "listing" }
      return cb
    end
  end
end

local function is_lead(b)
  if b.t ~= "Para" and b.t ~= "Plain" then return false end
  if #b.content == 1 and b.content[1].t == "Strong" then return true end
  return pandoc.utils.stringify(b):match(":%s*$") ~= nil
end

local function is_picture(b)
  if b.t == "Figure" then return true end
  return (b.t == "Para" or b.t == "Plain") and #b.content == 1 and b.content[1].t == "Image"
end

-- characters: a list this short stays with its lead-in; a table, whose rows
-- are short, can be longer and still fit a page
local SHORT = { BulletList = 700, OrderedList = 700, BlockQuote = 700, Table = 2000 }

local function keeps(b)
  if b.t == "CodeBlock" or is_picture(b) then return true end
  return SHORT[b.t] ~= nil and #pandoc.utils.stringify(b) <= SHORT[b.t]
end

function Blocks(blocks)
  local out, i = pandoc.Blocks({}), 1
  while i <= #blocks do
    local b, nxt = blocks[i], blocks[i + 1]
    if nxt and is_lead(b) and keeps(nxt) then
      out:insert(pandoc.Div({ b, nxt }, pandoc.Attr("", { "keep" })))
      i = i + 2
    else
      out:insert(b)
      i = i + 1
    end
  end
  return out
end
