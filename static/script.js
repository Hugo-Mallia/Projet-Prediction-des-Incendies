document.getElementById('uploadForm').addEventListener('submit', async function(event) {
    event.preventDefault();

    const fileInput = document.getElementById('imageUpload');
    const file = fileInput.files[0];

    const formData = new FormData();
    formData.append('image', file);

    try {
        const response = await fetch('/api/scan-environment/', {
            method: 'POST',
            body: formData
        });

        const risks = await response.json();
        const resultsDiv = document.getElementById('results');
        resultsDiv.innerHTML = '<h2>Résultats de l\'analyse :</h2>';

        risks.forEach(risk => {
            resultsDiv.innerHTML += `
                <div class="risk-item">
                    <p><strong>Label:</strong> ${risk.label}</p>
                    <p><strong>Confiance:</strong> ${risk.confidence}</p>
                    <p><strong>Emplacement:</strong> ${JSON.stringify(risk.location)}</p>
                </div>
            `;
        });
    } catch (error) {
        console.error('Error:', error);
        alert('Une erreur est survenue lors de l\'analyse de l\'image.');
    }
});

document.getElementById("auditForm").addEventListener("submit", async function(event) {
    event.preventDefault(); // Empêche le rechargement de la page

    const formData = new FormData(this);

    try {
        const response = await fetch("/api/submit-audit", {
            method: "POST",
            body: formData,
        });

        const result = await response.json();

        // Générer les recommandations
        let recommendations = "<h3>Recommandations :</h3><ul>";
        result.recommendations.forEach(rec => {
            recommendations += `<li>${rec}</li>`;
        });
        recommendations += "</ul>";

        // Afficher le compte rendu
        const auditMessage = `
            <strong>Status :</strong> ${result.status}<br>
            <strong>Message :</strong> ${result.message}<br><br>
            <strong>Résumé des informations saisies :</strong><br>
            <strong>Nom du bâtiment :</strong> ${result.data.buildingName}<br>
            <strong>Nombre d'extincteurs :</strong> ${result.data.fireExtinguishers}<br>
            <strong>Nombre de sorties de secours :</strong> ${result.data.emergencyExits}<br>
            <strong>Nombre de détecteurs de fumée :</strong> ${result.data.smokeDetectors}<br>
            <strong>Taille du bâtiment :</strong> ${result.data.buildingSize} m²<br>
            <strong>Nombre de pièces :</strong> ${result.data.roomCount}<br>
            <strong>Tailles des pièces :</strong> ${result.data.roomSizes.join(", ")} m²<br>
            ${recommendations}
        `;
        document.getElementById("auditMessage").innerHTML = auditMessage;
        document.getElementById("auditResult").style.display = "block";
    } catch (error) {
        console.error("Erreur lors de l'envoi de l'audit :", error);
        alert("Une erreur est survenue lors de l'envoi de l'audit.");
    }
});

function toggleAuditSections() {
    const usage = document.getElementById('buildingUsage').value;
    document.getElementById('habitationSection').style.display = usage === 'personnel' ? 'block' : 'none';
    document.getElementById('entrepriseSection').style.display = usage === 'professionnel' ? 'block' : 'none';
}
window.onload = toggleAuditSections;


// Create animated particles
function createParticles() {
    const particlesContainer = document.getElementById('particles');
    const particleCount = 50;

    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.top = Math.random() * 100 + '%';
        particle.style.width = particle.style.height = Math.random() * 4 + 1 + 'px';
        particle.style.animationDelay = Math.random() * 6 + 's';
        particle.style.animationDuration = (Math.random() * 3 + 3) + 's';
        particlesContainer.appendChild(particle);
    }
}

// Drag and drop functionality
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('imageUpload');

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        updateUploadText(files[0].name);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        updateUploadText(e.target.files[0].name);
    }
});

function updateUploadText(filename) {
    const uploadText = document.querySelector('.upload-text');
    uploadText.textContent = `Fichier sélectionné: ${filename}`;
    uploadArea.style.borderColor = '#4CAF50';
    uploadArea.style.background = 'rgba(76, 175, 80, 0.05)';
}

function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.style.background = type === 'success' ? '#4CAF50' : '#f44336';
    notification.classList.add('show');
    
    setTimeout(() => {
        notification.classList.remove('show');
    }, 3000);
}

function showProgress() {
    const progressBar = document.getElementById('progressBar');
    const progressFill = document.getElementById('progressFill');
    progressBar.style.display = 'block';
    
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 10;
        if (progress > 90) progress = 90;
        progressFill.style.width = progress + '%';
        
        if (progress >= 90) {
            clearInterval(interval);
        }
    }, 200);
    
    return interval;
}

function hideProgress() {
    const progressBar = document.getElementById('progressBar');
    const progressFill = document.getElementById('progressFill');
    progressFill.style.width = '100%';
    setTimeout(() => {
        progressBar.style.display = 'none';
        progressFill.style.width = '0%';
    }, 500);
}

// Form submission with enhanced UX
document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const scanText = document.getElementById('scanText');
    const originalText = scanText.textContent;
    const submitBtn = e.target.querySelector('button[type="submit"]');
    
    // Show loading state
    scanText.innerHTML = '<span class="loading"></span>Analyse en cours...';
    submitBtn.disabled = true;
    
    const progressInterval = showProgress();
    
    const formData = new FormData();
    formData.append('image', fileInput.files[0]);
    
    try {
        const response = await fetch('/predict', {
            method: 'POST',
            body: formData
        });
        
        hideProgress();
        clearInterval(progressInterval);
        
        if (response.ok) {
            const result = await response.json();
            displayResults(result);
            showNotification('Analyse terminée avec succès !');
        } else {
            throw new Error('Erreur lors de l\'analyse');
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('Erreur lors de l\'analyse. Veuillez réessayer.', 'error');
    } finally {
        // Reset button state
        scanText.textContent = originalText;
        submitBtn.disabled = false;
        hideProgress();
    }
});

function displayResults(result) {
    const resultsDiv = document.getElementById('results');
    let html = '<h3 style="color: #ff6b35; margin-bottom: 20px;"><i class="fas fa-chart-line"></i> Résultats de l\'Analyse</h3>';
    
    if (result.risks && result.risks.length > 0) {
        result.risks.forEach(risk => {
            html += `
                <div class="risk-item">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>${risk.type}</strong>
                            <p style="margin: 5px 0; color: #666;">${risk.description}</p>
                        </div>
                        <div style="background: ${getRiskColor(risk.severity)}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.9em;">
                            ${risk.severity}
                        </div>
                    </div>
                </div>
            `;
        });
    } else {
        html += '<div class="risk-item" style="border-left-color: #4CAF50;"><i class="fas fa-check-circle" style="color: #4CAF50; margin-right: 10px;"></i>Aucun risque détecté dans cette image.</div>';
    }
    
    resultsDiv.innerHTML = html;
    resultsDiv.style.display = 'block';
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

function getRiskColor(severity) {
    switch(severity.toLowerCase()) {
        case 'élevé': case 'high': return '#f44336';
        case 'moyen': case 'medium': return '#ff9800';
        case 'faible': case 'low': return '#4CAF50';
        default: return '#9e9e9e';
    }
}

// Initialize particles on load
window.addEventListener('load', () => {
    createParticles();
});

// Add some interactive elements
document.querySelectorAll('.action-card').forEach(card => {
    card.addEventListener('mouseenter', () => {
        card.style.background = 'linear-gradient(135deg, #ffffff, #f8f9fa)';
    });
    
    card.addEventListener('mouseleave', () => {
        card.style.background = 'white';
    });
});