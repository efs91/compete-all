// Gestion dynamique du formulaire de phase selon le type sélectionné
// typesConfig doit être défini dans le template HTML avant ce script

function initPhaseForm() {
    const typeSelect = document.getElementById('type_id');
    const scoringClassementSection = document.getElementById('scoring-classement');
    const scoringMatchSection = document.getElementById('scoring-match');
    
    if (!typeSelect || typeof typesConfig === 'undefined') {
        console.warn('Phase form: missing elements or typesConfig');
        return;
    }
    
    // Appliquer la config initiale si un type est déjà sélectionné
    if (typeSelect.value) {
        updateScoringFields(typeSelect.value);
    }
    
    // Écouter les changements de type
    typeSelect.addEventListener('change', function() {
        updateScoringFields(this.value);
    });
    
    function updateScoringFields(typeId) {
        const config = typesConfig[typeId] || {};
        
        // Afficher/masquer selon la config
        if (scoringClassementSection) {
            scoringClassementSection.style.display = config.classement ? 'block' : 'none';
            // Désactiver les champs si masqués
            const inputs = scoringClassementSection.querySelectorAll('input, select');
            inputs.forEach(input => {
                input.disabled = !config.classement;
            });
        }
        
        if (scoringMatchSection) {
            scoringMatchSection.style.display = config.points ? 'block' : 'none';
            // Désactiver les champs si masqués
            const inputs = scoringMatchSection.querySelectorAll('input, select');
            inputs.forEach(input => {
                input.disabled = !config.points;
            });
        }
    }
}

// Initialiser au chargement de la page
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPhaseForm);
} else {
    initPhaseForm();
}
