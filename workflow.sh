#!/bin/bash
# Workflow Management Script for RIGEL Browser Agent
PYTHON_SCRIPT="sudo docker exec -it rigel-rigel-server-1 python /app/test_browser_agent_direct.py"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_help() {
    echo -e "${BLUE}RIGEL Workflow Manager${NC}"
    echo ""
    echo "Usage:"
    echo "  ./workflow.sh list                    - List all saved workflows"
    echo "  ./workflow.sh save <name> <task>      - Run task with AI and save as workflow"
    echo "  ./workflow.sh replay <name>           - Replay a saved workflow"
    echo "  ./workflow.sh replay-headless <name>  - Replay in headless mode (no window)"
    echo "  ./workflow.sh run <task>              - Run task with AI (prompt to save)"
    echo ""
    echo "Examples:"
    echo "  ./workflow.sh list"
    echo "  ./workflow.sh save \"YouTube Search\" \"go to youtube.com and search for AI\""
    echo "  ./workflow.sh replay \"YouTube Search\""
    echo "  ./workflow.sh run \"go to github.com and search for python\""
}

if [ $# -eq 0 ]; then
    print_help
    exit 0
fi

case "$1" in
    list)
        echo -e "${GREEN}Listing all workflows...${NC}"
        $PYTHON_SCRIPT list
        ;;
    save)
        if [ $# -lt 3 ]; then
            echo -e "${YELLOW}Usage: ./workflow.sh save <name> <task>${NC}"
            exit 1
        fi
        workflow_name="$2"
        shift 2
        task="$*"
        echo -e "${GREEN}Running task with AI and saving as: $workflow_name${NC}"
        $PYTHON_SCRIPT --save "$workflow_name" "$task"
        ;;
    replay)
        if [ $# -lt 2 ]; then
            echo -e "${YELLOW}Usage: ./workflow.sh replay <name>${NC}"
            exit 1
        fi
        workflow_name="$2"
        echo -e "${GREEN}Replaying workflow: $workflow_name${NC}"
        $PYTHON_SCRIPT --replay "$workflow_name"
        ;;
    replay-headless)
        if [ $# -lt 2 ]; then
            echo -e "${YELLOW}Usage: ./workflow.sh replay-headless <name>${NC}"
            exit 1
        fi
        workflow_name="$2"
        echo -e "${GREEN}Replaying workflow (headless): $workflow_name${NC}"
        $PYTHON_SCRIPT --replay "$workflow_name" --headless
        ;;
    run)
        if [ $# -lt 2 ]; then
            echo -e "${YELLOW}Usage: ./workflow.sh run <task>${NC}"
            exit 1
        fi
        shift
        task="$*"
        echo -e "${GREEN}Running task with AI: $task${NC}"
        $PYTHON_SCRIPT "$task"
        ;;
    help|--help|-h)
        print_help
        ;;
    *)
        echo -e "${YELLOW}Unknown command: $1${NC}"
        print_help
        exit 1
        ;;
esac
