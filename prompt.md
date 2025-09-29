# Prompts

This project is using `uv` as package management.
Use `steamlit` to create a chatbot.
Use `boto3` as the AWS Bedrock's lib.
Use `litellm` as the proxy of LLM APIs.
Use `python-dotenv` to read `.env` file, getting the environment parameters.

The application can do:

- Create a session
- Within the session, all of the conversitions will bring to the `litellm`'s complication by different roles.
- Close a session
- A switch "Memory" has two status `On`/`Off`
    - If it is `On`, You need:
        - When the session is closing, calling the LLM to give a summary of the session
        - When the session is creating, bringing the summary of the previous sessions
        - Note: if the memory is `On`, and we have A session closed, then bring to the B session. When B session closing, we need to summary A&B together.
    - If is is `Off`, You need:
        - Still calling the LLM to give a summary of the session, when the session is closing.
        - But do NOT bring them into the new session.
