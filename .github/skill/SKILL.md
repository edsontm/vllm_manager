---
name: vllm_manager
description: Web application to manage vLLM instances.
---

mandatory:
- Always apply SOLID principles in application design and implementation.
- Ensure the application is scalable and can handle multiple vLLM instances efficiently.
- Prioritize security, especially for user authentication and access control.
- All external access to vLLM instances, including inference API calls, model endpoints, and token-authenticated requests, MUST be routed only through ports 80 (HTTP redirected to HTTPS) and 443 (HTTPS) via nginx reverse proxy. Direct access to internal vLLM ports is forbidden and must be blocked at the network or firewall layer.
- Ensure coexistence with other services on the same server: avoid resource conflicts, port conflicts, and security overlap. Keep the app containerized for isolation and configure nginx routing without interfering with other workloads.
- Implement robust error handling and logging to support troubleshooting and reliability when multiple vLLM instances run concurrently.

main tasks:
- Create a web interface to manage vLLM instances.
- Implement start, stop, and monitoring functionality for vLLM instances.
- Integrate with a backend for instance lifecycle management.
- Ensure secure access to the management interface.
- Provide real-time status updates for vLLM instances.
- Implement logging and error handling for management operations.
- Design a user-friendly interface for easy navigation and control.
- Create a test interface to evaluate reliability and performance of vLLM instances.
- Create one endpoint per vLLM model that can be accessed by tokens.
- Build CRUD workflows to register users and manage their tokens for vLLM access.
- Create a request queue and execute vLLM requests in batches to maximize parallel processing across multiple token-authenticated vLLM connections.
- Use vLLM with PagedAttention and continuous batching to maximize GPU utilization.
- Implement a dashboard for status and performance metrics of connected vLLM instances.
- Allow users to configure batch and model parameters from the interface.
- Suggest speculative execution to optimize performance and reduce latency.
- Measure request context length and log it for performance analysis.
- Use average context length to suggest context-size adjustments for better performance and resource utilization.
- Connect to Hugging Face so users can access and manage a broad catalog of LLM models.
- List available Hugging Face models and allow users to select and deploy them in vLLM instances.
- Allow users to switch between models for their vLLM instances.
- Implement automatic model update and management workflows for deployed LLMs.
- Provide documentation and support for effective product usage.
- For each vLLM instance, provide connection examples that use token authentication and HTTPS on port 443 only; never expose raw internal ports in docs or code examples.
- Generate Markdown docs in a separate skill folder with a directory structure that mirrors the codebase for easy mapping and reference.
- Keep deployment containerized with Docker for consistent environments and easier scaling.
- Configure nginx reverse proxy as the sole ingress for endpoint and token-authenticated traffic: only ports 80 and 443 are public, vLLM containers bind to 127.0.0.1 only, and Docker mappings must use 127.0.0.1:<port>:<port> (not 0.0.0.0).
- Use /etc/nginx/nginx.conf as reference. You cannot alter global nginx config, but you must create /etc/nginx/sites-available/vllm_manager.conf with proper routing and authentication behavior.
- Consult other enabled configs in /etc/nginx/sites-available/ for server configuration examples.
- Keep the application maintainable and extensible for future updates.
