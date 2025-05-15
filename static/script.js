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
