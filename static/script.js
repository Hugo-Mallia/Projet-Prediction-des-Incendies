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
