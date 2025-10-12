# 🤖 K8s AI Assistant Setup Guide

## Overview
The K8s AI Assistant is a new tab in the dashboard that provides an interactive chatbot powered by Google Gemini AI to help with Kubernetes questions, troubleshooting, and best practices.

## ✅ What's Been Added

### 1. **New Tab: "🤖 K8s AI Assistant"**
- Interactive chat interface
- Context-aware conversations
- Kubernetes expertise built-in
- Real-time responses

### 2. **Features**
- ✅ Chat with AI about Kubernetes concepts
- ✅ Get troubleshooting help
- ✅ Ask about pod management
- ✅ Learn best practices
- ✅ Clear chat history
- ✅ Persistent conversation context

### 3. **Technology**
- **LLM**: Google Gemini Pro
- **Why Gemini?**
  - ✅ Free tier available (no credit card required)
  - ✅ Easy integration with Python
  - ✅ Good quality responses
  - ✅ Fast response times
  - ✅ Generous rate limits

## 🔧 Setup Instructions

### Step 1: Get Google API Key (Free)

1. Go to: https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Copy the API key (looks like: `AIzaSyD...`)

**Note**: No credit card required! Gemini has a generous free tier.

### Step 2: Configure API Key

Add the API key to your `.env` file:

```bash
# Edit .env file
nano .env

# Add this line (replace with your actual key):
GOOGLE_API_KEY=AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Or create `.env` from the example:
```bash
cd "/mnt/c/Users/aneja/Desktop/K8s AI Project"
cp .env.example .env
nano .env
# Add your GOOGLE_API_KEY
```

### Step 3: Install Dependencies

```bash
cd "/mnt/c/Users/aneja/Desktop/K8s AI Project"
source .lxvenv/bin/activate
pip install -r requirements.txt
```

This will install:
- `google-generativeai>=0.3.0` (Gemini AI library)
- All other existing dependencies

### Step 4: Restart Dashboard

```bash
# If dashboard is running, stop it (Ctrl+C)
# Then restart:
source .lxvenv/bin/activate
streamlit run app/dashboard.py
```

Or use the background method:
```bash
pkill -f streamlit
nohup streamlit run app/dashboard.py > streamlit.log 2>&1 &
```

### Step 5: Test the AI Assistant

1. Open dashboard: http://localhost:8501
2. Click on **"🤖 K8s AI Assistant"** tab
3. You should see: "Hi! I'm your K8s AI Assistant..."
4. Try asking: "What is a Kubernetes pod?"

## 🎯 Usage Examples

### Example Questions to Ask:

**Basics:**
- "What is a Kubernetes pod?"
- "Explain Kubernetes deployments"
- "What's the difference between a pod and a container?"

**Troubleshooting:**
- "My pod is stuck in Pending state. How do I debug it?"
- "Why is my pod constantly restarting?"
- "How do I check pod logs?"

**Resource Management:**
- "How do I set resource limits for a pod?"
- "What's the best way to allocate CPU and memory?"
- "How do I monitor resource usage?"

**Best Practices:**
- "What are Kubernetes best practices for production?"
- "How should I structure my deployments?"
- "What's the recommended way to handle secrets?"

## ⚠️ Troubleshooting

### Issue: "Google API Key not configured"

**Solution:**
1. Make sure `.env` file exists in project root
2. Add `GOOGLE_API_KEY=your-key-here`
3. Restart dashboard

### Issue: "google.generativeai not installed"

**Solution:**
```bash
source .lxvenv/bin/activate
pip install google-generativeai
```

### Issue: "API Key invalid" or "403 Forbidden"

**Solution:**
1. Check your API key is correct in `.env`
2. Make sure you copied the full key (no spaces)
3. Try generating a new key from Google AI Studio
4. Check if you've exceeded free tier limits

### Issue: Chat not responding

**Solution:**
1. Check internet connection
2. Verify API key is valid
3. Check browser console for errors (F12)
4. Try clearing chat and asking again

## 🎨 UI Features

### Chat Interface
- **User messages**: Appear on right side
- **AI responses**: Appear on left side with robot icon
- **Thinking indicator**: Shows "Thinking..." while AI processes

### Buttons
- **🗑️ Clear Chat**: Resets conversation history
- **ℹ️ About**: Shows information about the AI Assistant

### Smart Features
- **Context awareness**: AI remembers previous messages in conversation
- **Markdown support**: Responses formatted with code blocks, lists, etc.
- **Error handling**: Clear error messages if something goes wrong

## 💡 Tips for Best Results

1. **Be specific**: "How do I debug a CrashLoopBackOff pod?" vs "Help with pod"
2. **Provide context**: Mention your cluster setup, error messages, etc.
3. **Ask follow-ups**: AI remembers conversation context
4. **Use for learning**: Great for understanding Kubernetes concepts
5. **Clear chat**: Start fresh for unrelated topics

## 🔐 Security Notes

- ✅ API key stored in `.env` (not committed to Git)
- ✅ `.gitignore` already includes `.env`
- ✅ Conversations not stored permanently (session only)
- ⚠️ Don't paste sensitive data (passwords, tokens) into chat
- ⚠️ AI responses are general guidance, not security audits

## 📊 Free Tier Limits (Google Gemini)

**Free Tier Includes:**
- 60 requests per minute
- 1,500 requests per day
- No credit card required
- No expiration

**Good for:**
- Personal projects ✅
- Learning and experimentation ✅
- Small team use ✅
- Development and testing ✅

**If you need more:**
- Upgrade to paid tier for higher limits
- Or wait for rate limit reset (1 minute/1 day)

## 🚀 Alternative LLM Options

If you want to use a different LLM instead of Gemini:

### Option 1: OpenAI (GPT-4/GPT-3.5)
- **Pros**: Best quality responses, very capable
- **Cons**: Requires paid API key ($$$)
- **Setup**: Replace `google-generativeai` with `openai`

### Option 2: Anthropic Claude
- **Pros**: High quality, context-aware
- **Cons**: Requires API key, paid tier recommended
- **Setup**: Use `anthropic` Python library

### Option 3: Ollama (Local)
- **Pros**: Free, runs locally, no API key needed
- **Cons**: Requires powerful hardware, slower
- **Setup**: Install Ollama, use `llama2` or `mistral`

### Option 4: Azure OpenAI
- **Pros**: Enterprise features, Microsoft integration
- **Cons**: Requires Azure account
- **Setup**: Use `openai` with Azure endpoint

**Recommendation**: Stick with Gemini for now - it's free, fast, and easy!

## 📝 Next Steps

1. ✅ Get API key from Google
2. ✅ Add to `.env` file
3. ✅ Install dependencies
4. ✅ Restart dashboard
5. ✅ Test with a simple question
6. 🎉 Enjoy your AI assistant!

## 🐛 Known Issues

None yet! If you find any, let me know.

## 🎯 Future Enhancements (Ideas)

- [ ] Context from cluster (auto-detect pod issues)
- [ ] Execute kubectl commands suggested by AI
- [ ] Save favorite responses
- [ ] Share conversations
- [ ] Multi-model support (switch between Gemini/GPT)
- [ ] Voice input/output
- [ ] Integration with VM Status tab (analyze metrics)

---

**Last Updated**: October 11, 2025
**Status**: ✅ Ready to use! Just add your API key.
