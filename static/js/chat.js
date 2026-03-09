// HealSmart Chat JavaScript

let currentChatId = null;

// Toggle Sidebar
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobileOverlay');
    
    sidebar.classList.toggle('hidden');
    overlay.classList.toggle('show');
}

// Auto-resize textarea
const chatInput = document.getElementById('chatInput');
if (chatInput) {
    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 200) + 'px';
    });
}

// Handle Enter key
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Send Message
function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;

    // Hide welcome screen
    const welcomeScreen = document.getElementById('welcomeScreen');
    if (welcomeScreen) {
        welcomeScreen.remove();
    }

    // If no current chat, create new one
    if (!currentChatId) {
        currentChatId = Date.now();
    }

    // Add user message
    addMessage(message, 'user');
    input.value = '';
    input.style.height = 'auto';

    // Show typing indicator
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.classList.add('show');
    }
    scrollToBottom();

    // Send to backend (Django)
    fetch('/api/chat/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            message: message,
            chat_id: currentChatId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (typingIndicator) {
            typingIndicator.classList.remove('show');
        }
        addMessage(data.response, 'bot');
    })
    .catch(error => {
        console.error('Error:', error);
        if (typingIndicator) {
            typingIndicator.classList.remove('show');
        }
        addMessage('Sorry, something went wrong. Please try again.', 'bot');
    });
}

// Add Message to Chat
function addMessage(text, sender) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    // Get user initial from page or default
    const userElement = document.querySelector('.user-avatar-nav');
    const userInitial = userElement ? userElement.textContent : 'U';
    
    const avatar = sender === 'bot' ? '🤖' : userInitial;
    const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-bubble">${escapeHtml(text)}</div>
            <div class="message-time">${time}</div>
        </div>
    `;
    
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        messagesContainer.insertBefore(messageDiv, typingIndicator);
    } else {
        messagesContainer.appendChild(messageDiv);
    }
    
    scrollToBottom();
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Scroll to Bottom
function scrollToBottom() {
    const messagesContainer = document.getElementById('chatMessages');
    if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

// Get CSRF Token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Initialize on page load
window.addEventListener('load', function() {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.focus();
    }
    
    // Close sidebar on mobile by default
    if (window.innerWidth <= 768) {
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
            sidebar.classList.add('hidden');
        }
    }
});

// Handle window resize
window.addEventListener('resize', function() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobileOverlay');
    
    if (window.innerWidth > 768) {
        sidebar.classList.remove('hidden');
        overlay.classList.remove('show');
    } else {
        sidebar.classList.add('hidden');
        overlay.classList.remove('show');
    }
});