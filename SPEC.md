# SPEC: Biotech News Monitoring Agent

## Goal

Build an agent that automatically keeps track of biotech and FDA news so
I do not have to check it manually. It should read news from a few
sources, use AI to summarize what matters, and show me the results.

The point is to have something that runs on its own on a schedule,
instead of me searching and reading everything by hand.

## Rough idea of how it works

- Pull in news from some news sources.
- Use an AI model to summarize each item and decide if it is relevant.
- Save the relevant ones somewhere I can look at them.
- Run this automatically on a schedule, not manually.

## Notes / open questions

- What counts as "relevant"? Need to define the topics.
- Where do the news sources come from? RSS, an API, scraping?
- Where do results get stored and shown?
- What happens when a source is down or the AI call fails?
- How does it avoid summarizing the same article twice?
