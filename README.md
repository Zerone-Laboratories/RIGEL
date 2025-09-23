# NSBM X Verisimilitude

### RIGEL-Engine-NSBM

## Web Server API Endpoints

The RIGEL Web Service provides various endpoints for different functionalities. All endpoints except the root (`/`) and license-info require API key authentication.

### Service Information

- **GET /** - Service information (no auth required)
  - Returns basic information about the service including version and available endpoints

### Core Inference Endpoints

- **POST /query** - Basic inference
  - Perform standard inference with the RIGEL engine
  - Requires API key

- **POST /query-with-memory** - Inference with memory persistence
  - Perform inference while maintaining conversation history
  - Requires API key

- **POST /query-think** - Advanced reasoning 
  - Perform inference with additional thinking steps
  - Requires API key

- **POST /query-with-tools** - Tool-augmented inference
  - Perform inference with access to external tools and functions
  - Requires API key

### Media Processing

- **POST /synthesize-text** - Text-to-speech synthesis
  - Convert text to audio
  - Requires API key

- **POST /recognize-audio** - Speech recognition
  - Convert audio to text
  - Requires API key

### NSBM GPA Calculation Endpoints

- **POST /nsbm/gpa/calculate** - Calculate NSBM GPA with detailed analysis
  - Parameters:
    - `course_names`: List of course names
    - `credits`: List of credit hours for each course
    - `grades`: List of NSBM grades (A+, A, A-, B+, B, B-, C+, C, C-, D+, D, F) or percentages (0-100)
  - Requires API key

- **POST /nsbm/gpa/simple** - Simple NSBM GPA calculation using grade points
  - Parameters:
    - `credits`: List of credit hours
    - `grade_points`: List of grade point values (0.0-4.0)
  - Requires API key

- **POST /nsbm/gpa/grade-info** - Get detailed NSBM grade information and classification
  - Parameters:
    - `grade`: NSBM grade to analyze
  - Requires API key

- **GET /nsbm/gpa/help** - Get help information about NSBM GPA calculation features
  - Returns detailed information about the GPA calculation API, including endpoints and the NSBM grading scale

### Administrative Endpoints

- **POST /admin/create-key** - Create API key for a tenant
  - Requires admin API key

- **GET /admin/usage/{tenant_id}** - Get usage statistics for a tenant
  - Requires admin API key

- **GET /admin/list-tenants** - List all tenants
  - Requires admin API key

- **POST /admin/switch-inference-engine** - Switch inference engine
  - Requires admin API key

- **GET /admin/current-inference-engine** - Get current inference engine
  - Requires admin API key

### Other Endpoints

- **GET /license-info** - License information (no auth required)
  - Returns licensing details for the service

## CURL Examples

Below are comprehensive examples of how to use the API endpoints with curl.

### Generate an API Key (Admin)

```bash
curl -X POST "http://localhost:8000/admin/create-key" \
     -H "Content-Type: application/json" \
     -H "X-Admin-Key: YOUR_ADMIN_KEY" \
     -d '{
       "name": "Test User",
       "plan": "free"
     }'
```

Response:
```json
{
  "api_key": "rigel_generated_key_here",
  "tenant_id": 1,
  "plan": "free"
}
```

### Basic Inference

```bash
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{
       "query": "What is the capital of France?"
     }'
```

Response:
```json
{
  "response": "The capital of France is Paris."
}
```

### Inference with Memory

```bash
curl -X POST "http://localhost:8000/query-with-memory" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{
       "query": "Tell me about France",
       "conversation_id": "conv123",
       "reset_conversation": false
     }'
```

### Advanced Inference Examples

#### Query with Thinking

```bash
curl -X POST "http://localhost:8000/query-think" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{
       "query": "Explain quantum computing in simple terms"
     }'
```

#### Query with Tools

```bash
curl -X POST "http://localhost:8000/query-with-tools" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{
       "query": "What is the weather in Colombo today?"
     }'
```

### Media Processing Examples

#### Text-to-Speech

```bash
curl -X POST "http://localhost:8000/synthesize-text" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{
       "text": "Welcome to NSBM Green University",
       "mode": "standard"
     }' \
     --output speech.wav
```

#### Speech Recognition

```bash
curl -X POST "http://localhost:8000/recognize-audio" \
     -H "X-API-Key: YOUR_API_KEY" \
     -F "audio_file=@/path/to/your/audio.wav" \
     -F "model=medium"
```

Response:
```json
{
  "text": "Welcome to NSBM Green University"
}
```

### NSBM GPA Calculation Examples

#### Calculate Detailed GPA

```bash
curl -X POST "http://localhost:8000/nsbm/gpa/calculate" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{
       "course_names": ["Mathematics", "Programming", "Physics"],
       "credits": [3, 4, 3],
       "grades": ["A", "B+", "A-"]
     }'
```

Response:
```json
{
  "gpa": 3.67,
  "total_credits": 10,
  "grade_points": 36.7,
  "letter_grade": "A-",
  "classification": "First Class Honours",
  "detailed_courses": [
    {
      "course": "Mathematics",
      "credits": 3,
      "grade": "A",
      "points": 12.0
    },
    {
      "course": "Programming",
      "credits": 4,
      "grade": "B+",
      "points": 13.2
    },
    {
      "course": "Physics",
      "credits": 3,
      "grade": "A-",
      "points": 11.1
    }
  ]
}
```

#### Simple GPA Calculation

```bash
curl -X POST "http://localhost:8000/nsbm/gpa/simple" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{
       "credits": [3, 4, 3],
       "grade_points": [4.0, 3.3, 3.7]
     }'
```

#### Get Grade Information

```bash
curl -X POST "http://localhost:8000/nsbm/gpa/grade-info" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{
       "grade": "B+"
     }'
```

Response:
```json
{
  "grade": "B+",
  "gpa": 3.3,
  "percentage_range": "80-84%",
  "classification": "Second Class Honours - Upper"
}
```

#### Get GPA Help Information

```bash
curl -X GET "http://localhost:8000/nsbm/gpa/help" \
     -H "X-API-Key: YOUR_API_KEY"
```

### Administrative Endpoints

#### Get Usage for a Tenant

```bash
curl -X GET "http://localhost:8000/admin/usage/1" \
     -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

#### List All Tenants

```bash
curl -X GET "http://localhost:8000/admin/list-tenants" \
     -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

#### Switch Inference Engine

```bash
curl -X POST "http://localhost:8000/admin/switch-inference-engine" \
     -H "Content-Type: application/json" \
     -H "X-Admin-Key: YOUR_ADMIN_KEY" \
     -d '{
       "engine": "ollama"
     }'
```

#### Get Current Inference Engine

```bash
curl -X GET "http://localhost:8000/admin/current-inference-engine" \
     -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

## NSBM Grading Scale

The service uses the following NSBM grading scale for GPA calculations:

| Grade | GPA | Percentage | Classification |
|-------|-----|------------|----------------|
| A+    | 4.0 | 90-100%    | First Class Honours |
| A     | 4.0 | 90-100%    | First Class Honours |
| A-    | 3.7 | 85-89%     | First Class Honours |
| B+    | 3.3 | 80-84%     | Second Class Honours - Upper |
| B     | 3.0 | 75-79%     | Second Class Honours - Lower |
| B-    | 2.7 | 70-74%     | Second Class Honours - Lower |
| C+    | 2.3 | 65-69%     | General Pass |
| C     | 2.0 | 60-64%     | General Pass |
| C-    | 1.7 | 55-59%     | General Pass |
| D+    | 1.3 | 50-54%     | General Pass |
| D     | 1.0 | 45-49%     | General Pass |
| F     | 0.0 | 0-44%      | Fail |