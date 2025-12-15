// Git tree visualization component
class GitTreeVisualizer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        
        // Author type colors scheme
        this.authorColors = {
            'end_user': '#4aa3ff',      // Blue - End User
            'pm_agent': '#4affb5',       // Green - PM Agent
            'planning_agent': '#feca57', // Yellow - Planning Agent
            'devops_agent': '#ee5a24',   // Orange - DevOps Agent
            'coder_agent': '#a55eea',    // Purple - Coder Agent
            'default': '#95afc0'         // Gray - Default/Unknown
        };
        
        // Branch colors for visual distinction
        this.branchColors = new Map();
        this.defaultBranchColors = [
            '#48dbfb', // cyan
            '#f368e0', // pink
            '#ff6b6b', // red
            '#32ff7e', // mint green
            '#7d5fff', // violet
        ];
        this.currentColorIndex = 0;
    }
    
    getAuthorType(author, email) {
        // Determine author type based on author name or email patterns
        const authorLower = author.toLowerCase();
        const emailLower = (email || '').toLowerCase();
        
        // Check for agent patterns in author name or email
        if (authorLower.includes('pm') || emailLower.includes('pm@')) {
            return 'pm_agent';
        } else if (authorLower.includes('planning') || emailLower.includes('planning@')) {
            return 'planning_agent';
        } else if (authorLower.includes('devops') || emailLower.includes('devops@')) {
            return 'devops_agent';
        } else if (authorLower.includes('coder') || authorLower.includes('bot') || emailLower.includes('coder@')) {
            return 'coder_agent';
        } else if (authorLower.includes('user') || !emailLower.includes('@agent')) {
            return 'end_user';
        }
        
        return 'default';
    }
    
    getAuthorColor(author, email) {
        const authorType = this.getAuthorType(author, email);
        return this.authorColors[authorType];
    }

    getBranchColor(branchName) {
        if (!this.branchColors.has(branchName)) {
            this.branchColors.set(branchName, this.defaultBranchColors[this.currentColorIndex % this.defaultBranchColors.length]);
            this.currentColorIndex++;
        }
        return this.branchColors.get(branchName);
    }

    renderTree(gitData) {
        if (!this.container) return;
        
        this.container.innerHTML = '';
        
        if (!gitData || !gitData.commits) {
            this.container.innerHTML = '<div class="git-tree-empty">No commits to display</div>';
            return;
        }

        // Create SVG for branch lines
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.classList.add('git-tree-svg');
        
        // Create commits container
        const commitsContainer = document.createElement('div');
        commitsContainer.classList.add('git-tree-commits');
        
        // Calculate positions for branches
        const branchLanes = new Map();
        let maxLane = 0;
        
        gitData.commits.forEach((commit, index) => {
            const branches = commit.branches || [];
            branches.forEach(branch => {
                if (!branchLanes.has(branch)) {
                    branchLanes.set(branch, maxLane++);
                }
            });
        });
        
        const laneWidth = 30;
        const commitHeight = 60;
        const totalWidth = Math.max(150, (maxLane + 1) * laneWidth + 100);
        const totalHeight = gitData.commits.length * commitHeight;
        
        svg.setAttribute('width', totalWidth);
        svg.setAttribute('height', totalHeight);
        svg.style.position = 'absolute';
        svg.style.left = '0';
        svg.style.top = '0';
        
        // Draw branch lines
        const drawnPaths = new Map();
        
        gitData.commits.forEach((commit, index) => {
            const y = index * commitHeight + commitHeight / 2;
            const branches = commit.branches || [];
            
            branches.forEach(branch => {
                const lane = branchLanes.get(branch);
                const x = lane * laneWidth + 20;
                const color = this.getBranchColor(branch);
                
                // Draw commit circle
                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('cx', x);
                circle.setAttribute('cy', y);
                circle.setAttribute('r', 5);
                circle.setAttribute('fill', color);
                circle.setAttribute('stroke', color);
                circle.setAttribute('stroke-width', '2');
                svg.appendChild(circle);
                
                // Draw connecting lines to next commit
                if (index < gitData.commits.length - 1) {
                    const nextCommit = gitData.commits[index + 1];
                    const nextBranches = nextCommit.branches || [];
                    
                    if (nextBranches.includes(branch)) {
                        const nextY = (index + 1) * commitHeight + commitHeight / 2;
                        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                        line.setAttribute('x1', x);
                        line.setAttribute('y1', y);
                        line.setAttribute('x2', x);
                        line.setAttribute('y2', nextY);
                        line.setAttribute('stroke', color);
                        line.setAttribute('stroke-width', '2');
                        svg.appendChild(line);
                    }
                }
                
                // Draw merge lines if this is a merge commit
                if (commit.parents && commit.parents.length > 1) {
                    commit.parents.slice(1).forEach(parentHash => {
                        const parentIndex = gitData.commits.findIndex(c => c.hash.startsWith(parentHash));
                        if (parentIndex > index) {
                            const parentY = parentIndex * commitHeight + commitHeight / 2;
                            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                            const d = `M ${x} ${y} Q ${x + 20} ${(y + parentY) / 2} ${x} ${parentY}`;
                            path.setAttribute('d', d);
                            path.setAttribute('stroke', color);
                            path.setAttribute('stroke-width', '2');
                            path.setAttribute('fill', 'none');
                            path.setAttribute('opacity', '0.6');
                            svg.appendChild(path);
                        }
                    });
                }
            });
        });
        
        // Create commit entries
        gitData.commits.forEach((commit, index) => {
            const commitEl = document.createElement('div');
            commitEl.classList.add('git-tree-commit');
            commitEl.style.height = commitHeight + 'px';
            commitEl.style.paddingLeft = (maxLane * laneWidth + 40) + 'px';
            
            const commitInfo = document.createElement('div');
            commitInfo.classList.add('git-commit-info');
            
            // Commit hash
            const hashEl = document.createElement('span');
            hashEl.classList.add('git-commit-hash');
            hashEl.textContent = commit.hash.substring(0, 7);
            
            // Commit message
            const messageEl = document.createElement('span');
            messageEl.classList.add('git-commit-message');
            messageEl.textContent = commit.message;
            
            // Author and date
            const metaEl = document.createElement('div');
            metaEl.classList.add('git-commit-meta');
            metaEl.textContent = `${commit.author} • ${this.formatDate(commit.date)}`;
            
            // Branch labels
            if (commit.branches && commit.branches.length > 0) {
                const branchesEl = document.createElement('div');
                branchesEl.classList.add('git-commit-branches');
                
                commit.branches.forEach(branch => {
                    const labelEl = document.createElement('span');
                    labelEl.classList.add('git-branch-label');
                    labelEl.style.backgroundColor = this.getBranchColor(branch);
                    labelEl.textContent = branch;
                    branchesEl.appendChild(labelEl);
                });
                
                commitInfo.appendChild(branchesEl);
            }
            
            // Tags
            if (commit.tags && commit.tags.length > 0) {
                const tagsEl = document.createElement('div');
                tagsEl.classList.add('git-commit-tags');
                
                commit.tags.forEach(tag => {
                    const tagEl = document.createElement('span');
                    tagEl.classList.add('git-tag-label');
                    tagEl.textContent = '🏷 ' + tag;
                    tagsEl.appendChild(tagEl);
                });
                
                commitInfo.appendChild(tagsEl);
            }
            
            commitInfo.appendChild(hashEl);
            commitInfo.appendChild(messageEl);
            commitInfo.appendChild(metaEl);
            
            commitEl.appendChild(commitInfo);
            commitsContainer.appendChild(commitEl);
        });
        
        // Add everything to container
        this.container.style.position = 'relative';
        this.container.appendChild(svg);
        this.container.appendChild(commitsContainer);
    }
    
    formatDate(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            if (diffHours === 0) {
                const diffMins = Math.floor(diffMs / (1000 * 60));
                return diffMins + ' minutes ago';
            }
            return diffHours + ' hours ago';
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return diffDays + ' days ago';
        } else if (diffDays < 30) {
            const weeks = Math.floor(diffDays / 7);
            return weeks + (weeks === 1 ? ' week ago' : ' weeks ago');
        } else {
            return date.toLocaleDateString();
        }
    }
}

// Export for use
window.GitTreeVisualizer = GitTreeVisualizer;
