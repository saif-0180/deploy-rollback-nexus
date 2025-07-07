#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Git Add, Commit, Push Script${NC}"
echo "=================================="

# Step 1: Git add all files
echo -e "${YELLOW}📁 Adding all files...${NC}"
git add --all :/

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Files added successfully${NC}"
else
    echo -e "${RED}❌ Failed to add files${NC}"
    exit 1
fi

# Step 2: Check if there are changes to commit
if git diff --cached --quiet; then
    echo -e "${YELLOW}⚠️  No changes to commit${NC}"
    exit 0
fi

# Step 3: Ask for commit message
echo -e "${YELLOW}💬 Enter your commit message:${NC}"
read -p "Commit message: " commit_message

# Check if commit message is empty
if [ -z "$commit_message" ]; then
    echo -e "${RED}❌ Commit message cannot be empty${NC}"
    exit 1
fi

# Step 4: Commit with the provided message
echo -e "${YELLOW}📝 Committing changes...${NC}"
git commit -m "$commit_message"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Commit successful${NC}"
else
    echo -e "${RED}❌ Commit failed${NC}"
    exit 1
fi

# Step 5: Push to remote
echo -e "${YELLOW}🚀 Pushing to remote...${NC}"
git push

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Push successful${NC}"
    echo -e "${BLUE}🎉 All done!${NC}"
else
    echo -e "${RED}❌ Push failed${NC}"
    exit 1
fi
