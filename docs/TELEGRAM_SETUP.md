# Telegram Bot Setup Guide

This guide will help you set up a Telegram bot for receiving trade alerts from SnipeTrade.

## Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Start a conversation with BotFather
3. Send the command: `/newbot`
4. Follow the prompts:
   - Choose a name for your bot (e.g., "My SnipeTrade Bot")
   - Choose a username for your bot (must end in 'bot', e.g., "mysnipetrade_bot")
5. BotFather will give you a **bot token** - save this! It looks like:
   ```
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789
   ```

## Step 2: Get Your Chat ID

### Method 1: Using @userinfobot

1. Search for **@userinfobot** in Telegram
2. Start a conversation with it
3. Send any message
4. The bot will reply with your user information, including your **Chat ID**
5. Copy the Chat ID (it will be a number like `123456789`)

### Method 2: Using Your Bot

1. Start a conversation with your newly created bot
2. Send any message to it (e.g., "Hello")
3. Open this URL in your browser (replace `YOUR_BOT_TOKEN`):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
4. Look for `"chat":{"id":XXXXXXX}` in the JSON response
5. The number is your Chat ID

### For Groups/Channels

If you want to send alerts to a group or channel:

1. Add your bot to the group/channel
2. Make the bot an admin (for channels)
3. Send a message in the group/channel
4. Use the `getUpdates` URL method above
5. The Chat ID will be negative (e.g., `-1001234567890`)

## Step 3: Configure SnipeTrade

### Option 1: Using Environment Variables (.env file)

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```bash
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789
   TELEGRAM_CHAT_ID=123456789
   ENABLE_NOTIFICATIONS=true
   ```

### Option 2: Using JSON Configuration

Edit your config file (e.g., `config/default.json`):

```json
{
  "telegram_bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
  "telegram_chat_id": "123456789",
  "enable_notifications": true
}
```

### Option 3: Using Command Line

```bash
snipetrade scan \
  --telegram-token "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789" \
  --telegram-chat-id "123456789"
```

## Step 4: Test Your Setup

Run a test scan:

```bash
snipetrade scan --max-pairs 5
```

You should receive:
1. A scan summary message when the scan completes
2. Individual trade setup alerts for top opportunities

## Message Format

You'll receive messages in this format:

```
🟢 BTC/USDT - LONG

📊 Score: 75.5/100
🎯 Confidence: 82%
💰 Entry: $50000.00

⏰ Timeframe Confluence:
  ✅ 15m: LONG
  ✅ 1h: LONG
  ✅ 4h: LONG

📈 Key Indicators:
  • RSI (1h): LONG
  • MACD (4h): LONG

💡 Analysis:
  • RSI shows LONG signal (strength: 0.80) on 1h
  • Multi-timeframe confluence across 15m, 1h, 4h

🏦 Exchange: phemex
```

## Customizing Alerts

### Control Number of Alerts

In your config file:

```json
{
  "top_setups_limit": 10,  // Max setups to find
  "min_score": 60.0        // Only alert on setups >= 60 score
}
```

### Disable Notifications Temporarily

Set in `.env`:
```bash
ENABLE_NOTIFICATIONS=false
```

Or in config:
```json
{
  "enable_notifications": false
}
```

## Troubleshooting

### "Unauthorized" Error
- Check that your bot token is correct
- Make sure there are no extra spaces in the token

### "Chat not found" Error
- Verify your Chat ID is correct
- Make sure you've sent at least one message to the bot first
- For groups, ensure the bot is added and has proper permissions

### Messages Not Appearing
- Check that `enable_notifications` is set to `true`
- Verify both bot token and chat ID are configured
- Check the audit logs in `./audit_logs/` for error messages

### Rate Limiting
- Telegram has rate limits (30 messages/second)
- SnipeTrade automatically adds delays between messages
- Reduce `top_setups_limit` if you're hitting limits

## Security Tips

1. **Never share your bot token** - it's like a password
2. **Use environment variables** for production
3. **Don't commit `.env` files** to version control (already in `.gitignore`)
4. **Regenerate token if exposed** - use `/revoke` with BotFather

## Advanced: Multiple Recipients

To send alerts to multiple chats:

1. Create multiple bot instances in your code, or
2. Add your bot to a group with all recipients, or
3. Use Telegram channels and add subscribers

## Future Trading Integration

When automated trading is enabled (future feature), you'll receive:
- Order execution confirmations
- Position updates
- Profit/loss notifications
- Risk management alerts

Keep your Telegram bot configured for seamless integration!
