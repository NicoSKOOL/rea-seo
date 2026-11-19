# REA SEO

Reverse engineer the #1 Google result for your keyword, side by side with your own page, and get a plan to take the spot. About $1 per keyword.

A free skill for Claude Code. Inspired by [REA (Reverse Engineer Anything)](https://github.com/morluto/rea), not affiliated with it.

![The report](docs/report.jpg)

## Why this exists

REA can take any app apart and show you how it was built. Point it at a #1 ranking page and it gets some of it right: the title, the heading outline, the links. But it can't see most of what Google reads: schema, meta description, speed, backlinks, the rest of the site, or whether AI answers mention you.

REA SEO does that missing half with [DataForSEO](https://app.dataforseo.com/?aff=182182) data.

## What it checks (the #1 vs you)

| Area | Examples |
|---|---|
| On-page SEO | Title, meta description, canonical, H1/H2s, schema, FAQ schema, image alt text |
| Agentic SEO / GEO | AI crawlers allowed, llms.txt, content readable without JavaScript, mentions in Google AI answers, named in ChatGPT's answer |
| Authority & brand | Linking sites (site and page), domain rank, domain age, brand searches, spam score, plus a link gap list |
| Pages & structure | Sitemap size, pages on the topic, URL depth, linked from the homepage, internal links |
| Content | Words, headings, keyword in the visible text |
| Speed | Lighthouse performance score, largest paint, layout shift |

Every row is a difference between two sites, not proof of why Google ranks one higher. Steal the strategy, never the content.

## Install

You need **Claude Code** (in the terminal, or the **Code** tab of the Claude desktop app), Python 3.9+, and a [DataForSEO account](https://app.dataforseo.com/?aff=182182) with a few dollars of credit.

**Easiest:** in Claude Code, paste:

> Install this skill: https://github.com/NicoSKOOL/rea-seo

**Or by hand** (Mac / Linux; on Windows use `%USERPROFILE%\.claude\skills\rea-seo`):

```bash
git clone https://github.com/NicoSKOOL/rea-seo ~/.claude/skills/rea-seo
pip install -r ~/.claude/skills/rea-seo/requirements.txt
```

Restart Claude Code so it picks up the skill.

## Use

Open Claude Code in the folder you want the results saved in and ask:

> Use REA SEO for "home appraiser virginia beach" against mysite.com, United States

The first time, it checks your setup and asks for your DataForSEO **API** login (from [app.dataforseo.com/api-access](https://app.dataforseo.com/api-access), not your website password). It saves it to `.env` inside the skill folder. It tells you the cost before it spends anything.

About 3 minutes later the report opens in your browser.

## What you get

Everything is saved in `rea-seo/<keyword>/package/` (plus a zip of it):

| File | Use it to |
|---|---|
| `report.html` | See the full #1 vs you teardown and the plan |
| `ACTION_PLAN.md` | Work through the plan as a checklist, with the evidence and a "done when" for each step |
| `data/link_gap.csv` | Pitch the sites that link to the #1 but not to you |
| `data/scores.csv`, `data/top10.csv` | Every check, and page one of Google |
| `data/baseline.json` | Today's numbers, so you can measure progress later |

Then drag the package folder into Claude or ChatGPT and say: *work through ACTION_PLAN.md one step at a time.*

## Good to know

- **Cost:** about $0.80 to $1.00 of DataForSEO credit per keyword. The report shows the real cost.
- **Any country:** pass any DataForSEO location code (2840 US, 2826 UK, 2036 AU, 2124 CA...).
- **Small markets:** DataForSEO traffic estimates are thin for small non-English markets. SERP and backlink data stay solid.
- **No rankings promised.** It shows you the gap and a plan. Closing gaps like backlinks and brand still takes real work.
- `yt-dlp` is optional. Without it, YouTube results on page one just show without view counts.

## Part of AI Ranking

This is one of the free tools from **AI Ranking**, the community where we learn how to get businesses found on Google and recommended by AI (ChatGPT, Google AI Overviews, Perplexity).

**Free community:** [skool.com/ai-ranking-free](https://skool.com/ai-ranking-free)  
Every free skill in one place, with setup guides.

**Premium:** [skool.com/ai-ranking](https://skool.com/ai-ranking)  
For when you want help, not just tools:
- Support when a skill or a site gets stuck
- 1-1 sessions
- Live Q&A calls
- The full training on how to rank in AI search

Built by [Nico Gorrono](https://airankingskool.com/about/)
