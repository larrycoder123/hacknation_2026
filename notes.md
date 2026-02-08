# Features

- Retrieve knowledge for a user question

## Knowledge insertion

### Where does the knowledge come from

- Chat is constantly being monitored and for every message sent the backend (a LLM) checks if the problem is solved. If it's solved, the knowledge is being inserted to the KB
- User can also provide manual feedback (problem solved or not). If solved, insert into KB

### How to process the knowledge

- Filter sensitive data stemming from the user
- Verify the knowledge does not manipulate/bias the existing KB

---

## Knowledge retrieval

- RAG -> Frontend: A list of suggested actions ordered by their confidence score