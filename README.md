# Price watch: a Claude skill

Type the skill name and a product. Claude finds the lowest price across the top stores and shows each store's price, star rating, stock and a buy link. If you want, it then keeps watching and tells you when the price drops.

```
/price-watch Sony WH-1000XM5
/price-watch AirPods Pro 2 USB-C
/price-watch Samsung 65" QN90D  (India)
```

It asks at most two quick questions, and only when it needs them: which variant, and which country.

## What you get

```
Sony WH-1000XM5 (Black, new). Lowest today: $279.99 at Target.

| Store    | Price   | Shipping | Rating      | In stock | Buy  |
|----------|---------|----------|-------------|----------|------|
| Target   | $279.99 | free     | 4.6★ (1.2k) | yes      | link |
| Amazon   | $298.00 | free     | 4.4★ (18k)  | yes      | link |
| Best Buy | $329.99 | free     | 4.7★ (3.4k) | yes      | link |
```

- **Works on every Claude plan, including Free.** All it needs is web search. It uses at most two searches and three page opens per lookup, so it stays cheap on tokens and messages.
- **Watch and alert.** You don't have to pick a target price: by default you hear about every new low.
  - On plans with artifacts, your products go on a live **Price Watch dashboard** that shows each store's price, the trend and buy links.
  - Where Claude can schedule tasks, it checks daily.
  - Elsewhere, just say "check my price watch".
- **Buy, safely.** Only from stores you allow, under a spending cap you set. Prices are compared including shipping and tax, and the cart is checked so nothing is added twice. **No order is ever placed without your live "yes"** after Claude shows the full summary.
- **Exact matches only.** Same model number, variant and condition (new) at every store. It skips unknown sites and suspiciously cheap listings.

Covers the main stores in the US (Amazon, Walmart, Best Buy, Target, Costco and more), India (Amazon.in, Flipkart, Croma, Reliance Digital, Tata CLiQ), the UK, and the largest stores elsewhere.

## Install

- **Claude.ai, any plan including Free**:
  1. Download [`dist/price-watch.zip`](dist/price-watch.zip).
  2. In Settings → Capabilities, turn on **Code execution and file creation** (called **Create and edit files** in newer layouts) and **Web search**.
  3. Upload the zip in **Customize → Skills**.
- **Claude Code**: copy the `price-watch/` folder into `~/.claude/skills/`.

## Inside

```
price-watch/
├── SKILL.md                  the workflow: questions, store comparison, watching, checks
├── assets/price-watch.html   the interactive dashboard (an artifact with a small database)
├── scripts/extract_price.py  reads price, stock and identifiers from a saved product page
├── scripts/update_watch.py   records a check across stores; decides new low / hit / drop
└── references/
    ├── buying.md             confirm-before-checkout rules (loaded only when buying)
    └── scheduling.md         recurring checks (loaded only when scheduling)
```

No card numbers, passwords or other secrets are stored anywhere.
