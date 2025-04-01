# Shopping Assistant with LLM

A modern online merchant website with a chatbot powered by GPT-4 that helps as a shopping assistant. The application uses a MCP servers for shopping and payment functionality.

## Architecture

The application consists of three main components:

1. Frontend (Streamlit)
   - Modern web interface with chat functionality
   - LLM agent powered by GPT-4
   - Communicates with backend servers via MCP

2. Shopping Backend
   - Handles inventory management
   - Shopping cart functionality
   - Exposes tools via MCP

3. Payment Backend
   - User authentication
   - Payment processing
   - Address management
   - Exposes tools via MCP

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up OpenAI API key:
```bash
export OPENAI_API_KEY='your-api-key-here'
```

3. Start the application:
```bash
cd frontend
streamlit run app.py
```

## Features

- Browse and search products
- Add items to cart
- View and manage shopping cart
- User authentication
- Payment processing
- Address management
- AI-powered shopping assistant

## Sample Usage

The shopping assistant can help with:

1. Browsing products:
   - "Show me all available items"
   - "Tell me more about the T-shirt"

2. Shopping cart:
   - "Add 2 T-shirts to my cart"
   - "What's in my cart?"

3. Checkout:
   - "I want to checkout"
   - "Show me my saved payment methods"
   - "Complete my purchase"

## Development

The application uses an architecture with MCP for inter-service communication. Each backend service exposes its functionality as MCP tools that can be used by the LLM agent.

### Project Structure

```
.
├── README.md
├── requirements.txt
├── mcp/
│   └── base.py
├── shopping/
│   └── server.py
├── payment/
│   └── server.py
└── frontend/
    └── app.py
``` 
