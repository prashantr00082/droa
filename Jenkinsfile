pipeline {
    agent any

    environment {
        // Provide the base URL for the local inference server (e.g. vLLM or Ollama routing)
        LOCAL_LLM_BASE_URL = 'http://llm-gateway.internal:8000/v1'
        LOCAL_LLM_API_KEY = credentials('local-llm-api-key')
        
        // Neo4j credentials if you want Jenkins to run the cypher script directly
        NEO4J_URI = 'bolt://neo4j.internal:7687'
        NEO4J_USER = credentials('neo4j-user')
        NEO4J_PASS = credentials('neo4j-password')
    }

    triggers {
        // Trigger on merge to main or PR updates, adjust based on Bitbucket webhook plugin configuration
        bitbucketPush()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Environment') {
            steps {
                sh '''
                python3 -m venv .venv
                source .venv/bin/activate
                pip install -r requirements.txt
                '''
            }
        }

        stage('Run DROA (Incremental)') {
            steps {
                // Since state is stored in .rkb/state.db which is committed to the repo,
                // this run is automatically incremental!
                sh '''
                source .venv/bin/activate
                python3 main.py .
                '''
            }
        }
        
        stage('Export Knowledge Graph') {
            steps {
                // Optionally execute the generated Cypher script against the remote Neo4j DB
                sh '''
                if [ -f "docs/load_graph.cypher" ]; then
                    echo "Loading graph into Neo4j..."
                    # Requires cypher-shell installed on the Jenkins agent
                    # cypher-shell -a $NEO4J_URI -u $NEO4J_USER -p $NEO4J_PASS -f docs/load_graph.cypher
                else
                    echo "No cypher script generated."
                fi
                '''
            }
        }

        stage('Commit Updated Knowledge Base') {
            steps {
                // Commit the updated .rkb/state.db and docs/ folder back to the repository
                sh '''
                git config --global user.name "DROA Jenkins Bot"
                git config --global user.email "droa@organization.internal"
                
                git add .rkb/state.db
                git add docs/
                
                # Check if there are changes to commit
                if ! git diff --cached --quiet; then
                    git commit -m "chore: auto-update Repository Knowledge Base [skip ci]"
                    # Push back to Bitbucket
                    git push origin HEAD:main
                else
                    echo "No changes in the Knowledge Base."
                fi
                '''
            }
        }
    }
    
    post {
        failure {
            echo "DROA Pipeline Failed!"
            // Add slackSend or email notification here
        }
    }
}
