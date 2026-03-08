// static/client.js
// Final version: polished RAG UI + persistent toggle + NER colors + resizer

document.addEventListener('DOMContentLoaded', () => {
    console.log("Client JS chargé (Version Finale).");

    // --- STATE ---
    let currentPatientId = null;
    let recognition = null;
    let isRecognizing = false;
    let pendingSendAfterStop = false;
    let historyCounter = 0;

    // Toggle state
    let currentDirtyText = "";
    let currentCleanText = "";
    let currentFilteredText = "";
    let viewMode = "filtered"; // filtered | clean | dirty
    let lastNonDirtyMode = "filtered";

    let liveFinalText = "";
    let liveInterimText = "";
    let liveDisplayText = "";
    let liveSessionId = null;
    let autosaveTimer = null;
    let manualStopRequested = false;
    const AUTOSAVE_MS = 5000;

    // --- DOM ---
    const drawer = document.getElementById('patientDrawer');
    const overlay = document.getElementById('drawerOverlay');
    const openDrawerBtn = document.getElementById('openDrawerBtn');
    const closeDrawerBtn = document.getElementById('closeDrawerBtn');
    const patientsListDiv = document.getElementById('patientsList');
    
    // New patient modal
    const newPatientModal = document.getElementById('newPatientModal');
    const openNewPatientModalBtn = document.getElementById('openNewPatientModalBtn');
    const closeNewPatientModalBtn = document.getElementById('closeNewPatientModalBtn');
    const cancelNewPatientBtn = document.getElementById('cancelNewPatientBtn');
    const newPatientForm = document.getElementById('newPatientForm');
    
    // Edit patient modal
    const editPatientModal = document.getElementById('editPatientModal');
    const closeEditPatientModalBtn = document.getElementById('closeEditPatientModalBtn');
    const cancelEditPatientBtn = document.getElementById('cancelEditPatientBtn');
    const editPatientForm = document.getElementById('editPatientForm');
    const applyPatientChangesBtn = document.getElementById('applyPatientChangesBtn');
    const deletePatientBtn = document.getElementById('deletePatientBtn');
    const activePatientBadge = document.getElementById('activePatientBadge');
    
    const noPatientOverlay = document.getElementById('noPatientOverlay');
    const activePatientName = document.getElementById('activePatientName');
    const docPatientName = document.getElementById('docPatientName');
    
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const statusDiv = document.getElementById('status');
    const statusIndicator = document.getElementById('statusIndicator');
    const resultDiv = document.getElementById('result');
    const visualizer = document.getElementById('visualizer');
    
    const localHistoryList = document.getElementById('localHistoryList');
    const emptyHistoryMsg = document.getElementById('emptyHistoryMsg');
    const selectAllCheckbox = document.getElementById('selectAllHistory');
    const historyCountLabel = document.getElementById('historyCount');

    const btnLaunchRag = document.getElementById('btnLaunchRag');
    const ragPlaceholder = document.getElementById('ragPlaceholder');
    const ragContent = document.getElementById('ragContent');
    const toggleViewBtn = document.getElementById('toggleViewBtn');
    const toggleBtnLabel = document.getElementById('toggleBtnLabel');
    const toggleDirtyBtn = document.getElementById('toggleDirtyBtn');
    const copyBtn = document.getElementById('copyBtn');
    const historySearchInput = document.getElementById('historySearchInput');

    const openFilterModalBtn = document.getElementById('openFilterModalBtn');
    const filterNotesModal = document.getElementById('filterNotesModal');
    const closeFilterModalBtn = document.getElementById('closeFilterModalBtn');
    const filterYearSelect = document.getElementById('filterYearSelect');
    const filterMonthSelect = document.getElementById('filterMonthSelect');
    const filterSearchInput = document.getElementById('filterSearchInput');
    const filterNotesList = document.getElementById('filterNotesList');
    const selectedNotesCount = document.getElementById('selectedNotesCount');
    const toggleSelectNotesBtn = document.getElementById('toggleSelectNotesBtn');

    const noteDetailModal = document.getElementById('noteDetailModal');
    const closeNoteDetailModalBtn = document.getElementById('closeNoteDetailModalBtn');
    const noteDetailDate = document.getElementById('noteDetailDate');
    const noteDetailContent = document.getElementById('noteDetailContent');
    const noteDetailCheckbox = document.getElementById('noteDetailCheckbox');
    const detailViewSummaryBtn = document.getElementById('detailViewSummaryBtn');
    const detailViewRawBtn = document.getElementById('detailViewRawBtn');
    const detailViewFilteredBtn = document.getElementById('detailViewFilteredBtn');

    let detailSummaryLines = [];
    let detailRawText = "";
    let detailFilteredText = "";
    let detailMode = "summary";

    const notesCache = [];
    const selectedNoteIds = new Set();
    let lastLoadedRecordings = [];

    const dragHandle = document.getElementById('dragHandle');
    const topPanel = document.getElementById('topPanel');
    const leftContainer = document.getElementById('leftColumnContainer');

    // ============================================
    // 1. NER FORMATTING (COLOR BADGES)
    // ============================================
    function formatFilteredText(text) {
        if (!text) return "";
        
        // Keep plain output if section markers are not present.
        if (!text.includes("###")) {
            return text;
        }

        let html = text;

        // 1. Render section titles with styled HTML.
        html = html.replace(/### (.*?)(?=\n|$)/g, (match, title) => {
            let colorClass = "text-slate-700 border-slate-200 bg-slate-50"; 
            
            // Title to color mapping.
            if (title.includes("SYMPTÔMES")) colorClass = "text-orange-700 bg-orange-50 border-orange-200";
            if (title.includes("TRAITEMENTS")) colorClass = "text-blue-700 bg-blue-50 border-blue-200";
            if (title.includes("PATHOLOGIES")) colorClass = "text-red-700 bg-red-50 border-red-200";
            if (title.includes("EXAMENS")) colorClass = "text-purple-700 bg-purple-50 border-purple-200";
            
            // Additional section colors.
            if (title.includes("CONTEXTE")) colorClass = "text-emerald-700 bg-emerald-50 border-emerald-200";
            if (title.includes("DONNÉES")) colorClass = "text-cyan-700 bg-cyan-50 border-cyan-200";

            return `<div class="mt-3 mb-1 font-bold text-[10px] uppercase tracking-wider border-b ${colorClass} px-2 py-1 rounded-t">${title}</div>`;
        });

        // 2. Render bullets as aligned rows.
        html = html.replace(/• (.*?)(?=\n|$)/g, '<div class="ml-2 pl-2 border-l-2 border-slate-100 text-sm text-slate-700 py-0.5">$1</div>');

        // 3. Remove remaining new lines.
        html = html.replace(/\n/g, '');

        return `<div class="font-sans">${html}</div>`;
    }

    // ============================================
    // 2. TOGGLE LOGIC & UI UPDATE
    // ============================================
    function updateResultView() {
        if (!resultDiv) return;

        if (viewMode === "dirty") {
            // DIRTY MODE (raw live text)
            resultDiv.innerText = currentDirtyText || "(Texte brut non disponible)";
            resultDiv.classList.add('text-slate-500', 'italic', 'font-sans');
            resultDiv.classList.remove('text-slate-800', 'font-serif');
            if(toggleBtnLabel) toggleBtnLabel.textContent = "Brut";
        } else if (viewMode === "clean") {
            // CLEAN MODE
            resultDiv.innerText = currentCleanText || "(Texte propre non disponible)";
            resultDiv.classList.add('text-slate-800', 'font-sans');
            resultDiv.classList.remove('text-slate-500', 'italic', 'font-serif');
            if(toggleBtnLabel) toggleBtnLabel.textContent = "Filtré";
        } else {
            // FILTERED MODE (NER)
            resultDiv.innerHTML = formatFilteredText(currentFilteredText);
            resultDiv.classList.add('text-slate-800', 'font-serif');
            resultDiv.classList.remove('text-slate-500', 'italic', 'font-sans');
            if(toggleBtnLabel) toggleBtnLabel.textContent = "Brut";
        }

        if (toggleViewBtn) {
            if (viewMode === "filtered") {
                toggleViewBtn.classList.replace('bg-slate-100', 'bg-brand-50');
                toggleViewBtn.classList.replace('text-slate-600', 'text-brand-600');
            } else {
                toggleViewBtn.classList.replace('bg-brand-50', 'bg-slate-100');
                toggleViewBtn.classList.replace('text-brand-600', 'text-slate-600');
            }
        }

        if (toggleDirtyBtn) {
            if (viewMode === "dirty") {
                toggleDirtyBtn.classList.add('bg-amber-50', 'text-amber-700', 'border-amber-200');
                toggleDirtyBtn.classList.remove('bg-slate-100', 'text-slate-600', 'border-slate-200');
            } else {
                toggleDirtyBtn.classList.remove('bg-amber-50', 'text-amber-700', 'border-amber-200');
                toggleDirtyBtn.classList.add('bg-slate-100', 'text-slate-600', 'border-slate-200');
            }
        }
    }

    if (toggleViewBtn) {
        toggleViewBtn.addEventListener('click', () => {
            if (!currentCleanText && !currentFilteredText) return;
            if (viewMode === "dirty") {
                viewMode = lastNonDirtyMode;
            }
            viewMode = (viewMode === "filtered") ? "clean" : "filtered";
            lastNonDirtyMode = viewMode;
            updateResultView();
        });
    }

    if (toggleDirtyBtn) {
        toggleDirtyBtn.addEventListener('click', () => {
            if (!currentDirtyText) return;
            if (viewMode !== "dirty") {
                lastNonDirtyMode = viewMode === "dirty" ? "filtered" : viewMode;
                viewMode = "dirty";
            } else {
                viewMode = lastNonDirtyMode;
            }
            updateResultView();
        });
    }

    if (historySearchInput) {
        historySearchInput.addEventListener('input', applyHistorySearchFilter);
    }

    function getNoteId(note) {
        return note?.id || note?.record_id || note?.note_id || note?.timestamp || note?.created_at;
    }

    function getNoteDate(note) {
        const ts = note?.timestamp || note?.created_at || note?.date;
        return ts ? new Date(ts) : null;
    }

    function ensureNoteInCache(note) {
        const id = getNoteId(note);
        if (!id) return;
        if (!notesCache.find(n => getNoteId(n) === id)) {
            notesCache.push(note);
        }
    }

    function updateSelectedCount() {
        if (selectedNotesCount) {
            selectedNotesCount.textContent = `${selectedNoteIds.size} notes sélectionnées`;
        }
        if (historyCountLabel) {
            const total = notesCache.length;
            historyCountLabel.textContent = total === 0 ? "0" : `${selectedNoteIds.size}/${total}`;
        }
        updateToggleSelectButton();
    }

    function setStatusIndicator(mode) {
        if (!statusIndicator) return;
        statusIndicator.classList.remove('bg-slate-300', 'bg-emerald-500', 'bg-amber-500', 'bg-red-500');
        if (mode === 'listening') statusIndicator.classList.add('bg-red-500');
        else if (mode === 'processing') statusIndicator.classList.add('bg-amber-500');
        else if (mode === 'ready') statusIndicator.classList.add('bg-emerald-500');
        else statusIndicator.classList.add('bg-slate-300');
    }

    function isPinned(noteId) {
        return localStorage.getItem(`note_pin_${noteId}`) === '1';
    }

    function togglePinned(noteId) {
        if (!noteId) return;
        const next = !isPinned(noteId);
        localStorage.setItem(`note_pin_${noteId}`, next ? '1' : '0');
        if (lastLoadedRecordings.length) {
            renderHistoryList(lastLoadedRecordings);
        }
    }

    function matchesSearch(note, query) {
        if (!query) return true;
        const text = `${note.title || ''} ${note.text || ''} ${note.text_raw || ''}`.toLowerCase();
        return text.includes(query);
    }

    function applyHistorySearchFilter() {
        const query = (historySearchInput?.value || '').trim().toLowerCase();
        document.querySelectorAll('.history-item').forEach(item => {
            const hay = item.dataset.search || '';
            item.style.display = !query || hay.includes(query) ? '' : 'none';
        });
    }

    function updateToggleSelectButton() {
        if (!toggleSelectNotesBtn) return;
        const total = notesCache.length;
        if (total > 0 && selectedNoteIds.size === total) {
            toggleSelectNotesBtn.textContent = "Tout désélectionner";
            toggleSelectNotesBtn.classList.remove('bg-brand-50', 'text-brand-600', 'border-brand-100');
            toggleSelectNotesBtn.classList.add('bg-slate-100', 'text-slate-600', 'border-slate-200');
        } else {
            toggleSelectNotesBtn.textContent = "Tout sélectionner";
            toggleSelectNotesBtn.classList.add('bg-brand-50', 'text-brand-600', 'border-brand-100');
            toggleSelectNotesBtn.classList.remove('bg-slate-100', 'text-slate-600', 'border-slate-200');
        }
    }

    function setNoteSelected(noteId, isSelected) {
        if (!noteId) return;
        if (isSelected) selectedNoteIds.add(noteId);
        else selectedNoteIds.delete(noteId);

        document.querySelectorAll(`[data-role="rag-checkbox"][data-note-id="${noteId}"]`).forEach(cb => {
            cb.checked = isSelected;
        });

        updateSelectedCount();
    }

    function buildFilterYearOptions() {
        if (!filterYearSelect) return;
        const years = new Set();
        notesCache.forEach(n => {
            const d = getNoteDate(n);
            if (d) years.add(d.getFullYear());
        });

        const current = filterYearSelect.value;
        filterYearSelect.innerHTML = `<option value="all">Toutes les années</option>` +
            [...years].sort((a, b) => b - a).map(y => `<option value="${y}">${y}</option>`).join("");
        filterYearSelect.value = current && current !== "all" ? current : "all";
    }

    function renderFilterList() {
        if (!filterNotesList) return;
        buildFilterYearOptions();

        const year = filterYearSelect?.value;
        const month = filterMonthSelect?.value;
        const query = (filterSearchInput?.value || '').trim().toLowerCase();

        const filtered = notesCache.filter(n => {
            const d = getNoteDate(n);
            if (!d) return true;
            if (year && year !== "all" && d.getFullYear() !== Number(year)) return false;
            if (month && month !== "all" && (d.getMonth() + 1) !== Number(month)) return false;
            return matchesSearch(n, query);
        });

        filterNotesList.innerHTML = filtered.map(n => {
            const id = getNoteId(n);
            const d = getNoteDate(n);
            const dateText = d ? d.toLocaleString("fr-FR") : (n.timestamp || "Date inconnue");
            const title = n.title || "Note";
            const pinned = isPinned(id);

            return `
                <div class="flex items-center justify-between border border-slate-200 rounded-lg p-2">
                    <div class="flex flex-col">
                        <span class="text-xs font-semibold text-slate-700">${title}</span>
                        <span class="text-[10px] text-slate-400">${dateText}</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <button class="pin-note-btn text-[10px] px-2 py-1 ${pinned ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-slate-100 text-slate-600 border-slate-200'} rounded border" data-action="pin-note" data-note-id="${id}">★</button>
                        <button class="text-[10px] px-2 py-1 bg-slate-100 rounded border border-slate-200" data-action="open-detail" data-note-id="${id}">!</button>
                        <input type="checkbox" class="w-4 h-4 text-brand-600 rounded border-slate-300 focus:ring-brand-500" data-role="rag-checkbox" data-note-id="${id}" ${selectedNoteIds.has(id) ? "checked" : ""} />
                    </div>
                </div>
            `;
        }).join("");

        updateSelectedCount();
    }

    function setDetailMode(mode) {
        detailMode = mode;
        if (!noteDetailContent) return;

        if (detailMode === "summary") {
            const items = detailSummaryLines.length
                ? detailSummaryLines.map(s => `<li>${s}</li>`).join("")
                : '<li>Aucun résumé disponible.</li>';
            noteDetailContent.innerHTML = `<ul class="list-disc pl-5 text-sm text-slate-700 space-y-1">${items}</ul>`;
        } else if (detailMode === "raw") {
            const text = detailRawText || "(Texte brut non disponible)";
            noteDetailContent.innerHTML = `<div class="text-xs text-slate-600 whitespace-pre-wrap">${text}</div>`;
        } else {
            const text = detailFilteredText || "(Texte filtré non disponible)";
            const formatted = formatFilteredText(text) || text;
            noteDetailContent.innerHTML = `<div class="text-xs text-slate-700">${formatted}</div>`;
        }

        if (detailViewSummaryBtn && detailViewRawBtn && detailViewFilteredBtn) {
            const isSummary = detailMode === "summary";
            const isRaw = detailMode === "raw";
            const isFiltered = detailMode === "filtered";

            detailViewSummaryBtn.classList.toggle('bg-brand-50', isSummary);
            detailViewSummaryBtn.classList.toggle('text-brand-600', isSummary);
            detailViewSummaryBtn.classList.toggle('border-brand-100', isSummary);

            detailViewRawBtn.classList.toggle('bg-brand-50', isRaw);
            detailViewRawBtn.classList.toggle('text-brand-600', isRaw);
            detailViewRawBtn.classList.toggle('border-brand-100', isRaw);

            detailViewFilteredBtn.classList.toggle('bg-brand-50', isFiltered);
            detailViewFilteredBtn.classList.toggle('text-brand-600', isFiltered);
            detailViewFilteredBtn.classList.toggle('border-brand-100', isFiltered);
        }
    }

    async function openDetail(note) {
        const id = getNoteId(note);
        if (!id || !noteDetailModal) return;

        const rawText = note.text_raw || note.raw || "";
        const filteredText = note.text || note.filtered || "";
        const timestamp = note.timestamp || "";

        const res = await fetch("/api/note/summary", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: rawText, timestamp })
        });

        const data = await res.json();
        if (noteDetailDate) noteDetailDate.textContent = data.date || "Date inconnue";
        detailSummaryLines = data.summary || [];
        detailRawText = rawText || "";
        detailFilteredText = filteredText || "";
        setDetailMode("summary");

        if (noteDetailCheckbox) {
            noteDetailCheckbox.dataset.noteId = id;
            noteDetailCheckbox.checked = selectedNoteIds.has(id);
        }

        noteDetailModal.classList.remove('hidden');
        noteDetailModal.classList.add('flex');
    }

    if (openFilterModalBtn && filterNotesModal) {
        openFilterModalBtn.addEventListener('click', () => {
            renderFilterList();
            filterNotesModal.classList.remove('hidden');
            filterNotesModal.classList.add('flex');
        });
    }

    if (closeFilterModalBtn && filterNotesModal) {
        closeFilterModalBtn.addEventListener('click', () => {
            filterNotesModal.classList.add('hidden');
            filterNotesModal.classList.remove('flex');
        });
    }

    if (closeNoteDetailModalBtn && noteDetailModal) {
        closeNoteDetailModalBtn.addEventListener('click', () => {
            noteDetailModal.classList.add('hidden');
            noteDetailModal.classList.remove('flex');
        });
    }

    if (filterYearSelect) filterYearSelect.addEventListener('change', renderFilterList);
    if (filterMonthSelect) filterMonthSelect.addEventListener('change', renderFilterList);
    if (filterSearchInput) filterSearchInput.addEventListener('input', renderFilterList);

    if (toggleSelectNotesBtn) {
        toggleSelectNotesBtn.addEventListener('click', () => {
            const total = notesCache.length;
            const selectAll = !(total > 0 && selectedNoteIds.size === total);
            notesCache.forEach(n => setNoteSelected(getNoteId(n), selectAll));
            renderFilterList();
        });
    }

    if (filterNotesList) {
        filterNotesList.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action="open-detail"]');
            const pinBtn = e.target.closest('[data-action="pin-note"]');
            if (pinBtn) {
                togglePinned(pinBtn.dataset.noteId);
                renderFilterList();
                return;
            }
            if (!btn) return;
            const id = btn.dataset.noteId;
            const note = notesCache.find(n => getNoteId(n) === id);
            if (note) openDetail(note);
        });

        filterNotesList.addEventListener('change', (e) => {
            const cb = e.target.closest('[data-role="rag-checkbox"]');
            if (!cb) return;
            setNoteSelected(cb.dataset.noteId, cb.checked);
        });
    }

    if (noteDetailCheckbox) {
        noteDetailCheckbox.addEventListener('change', (e) => {
            const id = e.target.dataset.noteId;
            setNoteSelected(id, e.target.checked);
        });
    }

    if (detailViewSummaryBtn) detailViewSummaryBtn.addEventListener('click', () => setDetailMode("summary"));
    if (detailViewRawBtn) detailViewRawBtn.addEventListener('click', () => setDetailMode("raw"));
    if (detailViewFilteredBtn) detailViewFilteredBtn.addEventListener('click', () => setDetailMode("filtered"));

    const mainTitleInput = document.getElementById('noteTitleInput');
    if (mainTitleInput) {
        mainTitleInput.addEventListener('input', function() {
            const activeDiv = document.querySelector('.history-item.active');
            if (activeDiv) {
                const newTitle = mainTitleInput.value.trim() || activeDiv.dataset.title || 'Note';
                activeDiv.dataset.title = newTitle;
                const histInput = activeDiv.querySelector('.note-title-input');
                if (histInput) histInput.value = newTitle;
                const cacheItem = notesCache.find(n => getNoteId(n) === activeDiv.dataset.recordId);
                if (cacheItem) cacheItem.title = newTitle;
                localStorage.setItem(`note_title_${activeDiv.dataset.recordId}`, newTitle);
            }
        });
    }

    if (copyBtn) {
        copyBtn.addEventListener('click', async () => {
            let textToCopy = "";
            if (viewMode === "dirty") textToCopy = currentDirtyText;
            else if (viewMode === "clean") textToCopy = currentCleanText;
            else textToCopy = currentFilteredText;

            if (!textToCopy) return;
            try {
                await navigator.clipboard.writeText(textToCopy);
                statusDiv.textContent = "Copié.";
                setTimeout(() => { statusDiv.textContent = "Prêt"; }, 1500);
            } catch (e) {
                alert("Impossible de copier");
            }
        });
    }

    // ============================================
    // NEW PATIENT MODAL
    // ============================================
    function openNewPatientModal() {
        if (newPatientModal) newPatientModal.classList.remove('hidden');
    }
    
    function closeNewPatientModal() {
        if (newPatientModal) newPatientModal.classList.add('hidden');
        if (newPatientForm) newPatientForm.reset();
    }
    
    if (openNewPatientModalBtn) {
        openNewPatientModalBtn.addEventListener('click', openNewPatientModal);
    }
    
    if (closeNewPatientModalBtn) {
        closeNewPatientModalBtn.addEventListener('click', closeNewPatientModal);
    }
    
    if (cancelNewPatientBtn) {
        cancelNewPatientBtn.addEventListener('click', closeNewPatientModal);
    }
    
    // Close modal when clicking overlay.
    if (newPatientModal) {
        newPatientModal.addEventListener('click', (e) => {
            if (e.target === newPatientModal) closeNewPatientModal();
        });
    }
    
    // Submit form.
    if (newPatientForm) {
        newPatientForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Read form data.
            const formData = new FormData(newPatientForm);
            
            // Check selected date mode.
            const dateMode = formData.get('dateMode');
            let dateOfBirth = null;
            
            if (dateMode === 'birthdate') {
                dateOfBirth = formData.get('dateOfBirth');
            } else if (dateMode === 'age') {
                const age = formData.get('age');
                if (!age || age.trim() === '') {
                    alert('Veuillez remplir l\'âge estimé');
                    return;
                }
                // Convert estimated age to an approximate birth date.
                const today = new Date();
                const birthYear = today.getFullYear() - parseInt(age);
                dateOfBirth = `${birthYear}-01-01`;
            }
            
            const patientData = {
                firstName: formData.get('firstName'),
                lastName: formData.get('lastName'),
                dateOfBirth: dateOfBirth,
                dateMode: dateMode,
                age: dateMode === 'age' ? formData.get('age') : null,
                gender: formData.get('gender'),
                visitType: formData.get('visitType'),
                clinicalNote: formData.get('clinicalNote') || null,
                phone: formData.get('phone') || null,
                email: formData.get('email') || null,
                allergies: formData.get('allergies') || null,
                medicalHistory: formData.get('medicalHistory') || null,
                currentTreatment: formData.get('currentTreatment') || null,
                referenceNumber: formData.get('referenceNumber') || null
            };
            
            // Validate required fields.
            if (!patientData.firstName.trim() || !patientData.lastName.trim() || !patientData.dateOfBirth || !patientData.gender) {
                alert('Veuillez remplir tous les champs obligatoires');
                return;
            }
            
            try {
                // Send to backend.
                const resp = await fetch('/patients', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: `${patientData.firstName} ${patientData.lastName}`,
                        ...patientData
                    })
                });
                
                if (resp.ok) {
                    const patient = await resp.json();
                    console.log('Patient créé:', patient);
                    closeNewPatientModal();
                    // Reload patient list, then select newly created record.
                    await loadPatients();
                    selectPatient(patient);
                } else {
                    alert('Erreur lors de la création du patient');
                }
            } catch (err) {
                console.error('Erreur:', err);
                alert('Erreur lors de la création du patient');
            }
        });
    }
    
    // ============================================
    // EDIT PATIENT MODAL
    // ============================================
    let originalPatientData = {}; // Keep baseline values for dirty-checking.
    
    // Make active patient badge clickable.
    if (activePatientBadge) {
        activePatientBadge.addEventListener('click', async () => {
            if (!currentPatientId) return;
            await openEditPatientModal();
        });
    }
    
    async function openEditPatientModal() {
        try {
            // Load patient information.
            const resp = await fetch(`/patients/${currentPatientId}/info`);
            if (!resp.ok) throw new Error('Erreur chargement patient');
            
            const patientData = await resp.json();
            originalPatientData = { ...patientData }; // Copy to detect changes.
            
            // Populate form fields.
            document.getElementById('editFirstName').value = patientData.firstName || '';
            document.getElementById('editLastName').value = patientData.lastName || '';
            document.getElementById('editGender').value = patientData.gender === 'male' ? 'Mâle' : patientData.gender === 'female' ? 'Femelle' : '';
            document.getElementById('editDateOfBirth').value = patientData.dateOfBirth || '';
            editPatientForm.visitType.value = patientData.visitType || 'consultation';
            document.getElementById('editClinicalNote').value = patientData.clinicalNote || '';
            document.getElementById('editAllergies').value = patientData.allergies || '';
            document.getElementById('editMedicalHistory').value = patientData.medicalHistory || '';
            document.getElementById('editCurrentTreatment').value = patientData.currentTreatment || '';
            document.getElementById('editReferenceNumber').value = patientData.referenceNumber || '';
            
            // Keep apply button disabled until a change is detected.
            applyPatientChangesBtn.disabled = true;
            applyPatientChangesBtn.classList.add('bg-slate-400', 'cursor-not-allowed');
            applyPatientChangesBtn.classList.remove('bg-brand-600', 'hover:bg-brand-700');
            
            // Show modal.
            editPatientModal.classList.remove('hidden');
        } catch (err) {
            console.error('Erreur:', err);
            alert('Impossible de charger les infos du patient');
        }
    }
    
    function closeEditPatientModal() {
        if (editPatientModal) editPatientModal.classList.add('hidden');
        if (editPatientForm) editPatientForm.reset();
    }
    
    if (closeEditPatientModalBtn) {
        closeEditPatientModalBtn.addEventListener('click', closeEditPatientModal);
    }
    
    if (cancelEditPatientBtn) {
        cancelEditPatientBtn.addEventListener('click', closeEditPatientModal);
    }
    
    // Close modal when clicking overlay.
    if (editPatientModal) {
        editPatientModal.addEventListener('click', (e) => {
            if (e.target === editPatientModal) closeEditPatientModal();
        });
    }
    
    // Enable apply button only when form differs from baseline.
    if (editPatientForm) {
        editPatientForm.addEventListener('input', () => {
            const hasChanges = 
                editPatientForm.visitType.value !== originalPatientData.visitType ||
                document.getElementById('editDateOfBirth').value !== (originalPatientData.dateOfBirth || '') ||
                document.getElementById('editClinicalNote').value !== (originalPatientData.clinicalNote || '') ||
                document.getElementById('editAllergies').value !== (originalPatientData.allergies || '') ||
                document.getElementById('editMedicalHistory').value !== (originalPatientData.medicalHistory || '') ||
                document.getElementById('editCurrentTreatment').value !== (originalPatientData.currentTreatment || '') ||
                document.getElementById('editReferenceNumber').value !== (originalPatientData.referenceNumber || '');
            
            if (hasChanges) {
                applyPatientChangesBtn.disabled = false;
                applyPatientChangesBtn.classList.remove('bg-slate-400', 'cursor-not-allowed');
                applyPatientChangesBtn.classList.add('bg-brand-600', 'hover:bg-brand-700');
            } else {
                applyPatientChangesBtn.disabled = true;
                applyPatientChangesBtn.classList.add('bg-slate-400', 'cursor-not-allowed');
                applyPatientChangesBtn.classList.remove('bg-brand-600', 'hover:bg-brand-700');
            }
        });
        
        // Submit changes.
        editPatientForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(editPatientForm);
            const updatedData = {
                name: `${originalPatientData.firstName} ${originalPatientData.lastName}`,
                firstName: originalPatientData.firstName,
                lastName: originalPatientData.lastName,
                gender: originalPatientData.gender,
                dateOfBirth: formData.get('dateOfBirth'),
                visitType: formData.get('visitType'),
                clinicalNote: formData.get('clinicalNote') || null,
                allergies: formData.get('allergies') || null,
                medicalHistory: formData.get('medicalHistory') || null,
                currentTreatment: formData.get('currentTreatment') || null,
                referenceNumber: formData.get('referenceNumber') || null
            };
            
            try {
                const resp = await fetch(`/patients/${currentPatientId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updatedData)
                });
                
                if (resp.ok) {
                    alert('Modifications sauvegardées avec succès');
                    closeEditPatientModal();
                } else {
                    alert('Erreur lors de la sauvegarde');
                }
            } catch (err) {
                console.error('Erreur:', err);
                alert('Erreur lors de la sauvegarde');
            }
        });
    }
    
    // Delete patient.
    if (deletePatientBtn) {
        deletePatientBtn.addEventListener('click', async () => {
            if (!confirm(`⚠️ ATTENTION ! Vous allez supprimer définitivement ce patient et toutes ses notes. Cette action est irréversible. Continuer ?`)) return;
            
            try {
                const resp = await fetch(`/patients/${currentPatientId}`, {
                    method: 'DELETE'
                });
                
                if (resp.ok) {
                    alert('Patient supprimé avec succès');
                    closeEditPatientModal();
                    // Reload list and reset selection state.
                    currentPatientId = null;
                    if (activePatientName) activePatientName.textContent = 'Aucun patient sélectionné';
                    if (noPatientOverlay) noPatientOverlay.classList.remove('hidden');
                    await loadPatients();
                } else {
                    alert('Erreur lors de la suppression');
                }
            } catch (err) {
                console.error('Erreur:', err);
                alert('Erreur lors de la suppression');
            }
        });
    }
    
    // Date of birth / age mode toggle.
    const dateModeRadios = document.querySelectorAll('input[name="dateMode"]');
    const dateOfBirthWrapper = document.getElementById('dateOfBirthWrapper');
    const dateOfBirthInput = document.getElementById('dateOfBirthInput');
    const ageInputWrapper = document.getElementById('ageInputWrapper');
    const ageInput = document.getElementById('ageInput');
    
    dateModeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (e.target.value === 'birthdate') {
                dateOfBirthWrapper.classList.remove('hidden');
                dateOfBirthInput.required = true;
                ageInputWrapper.classList.add('hidden');
                ageInput.required = false;
            } else if (e.target.value === 'age') {
                dateOfBirthWrapper.classList.add('hidden');
                dateOfBirthInput.required = false;
                ageInputWrapper.classList.remove('hidden');
                ageInput.required = true;
            }
        });
    });
    // ============================================
    // 3. HISTORY UI (WITH RAW/FILTERED STORAGE)
    // ============================================
    function addToHistoryUI(id, text, textRaw, textClean, dim, timestamp, options = {}) {
        if (emptyHistoryMsg) emptyHistoryMsg.style.display = 'none';
        historyCounter++;

        const div = document.createElement('div');
        div.id = `rag-item-${id}`;
        div.dataset.recordId = id;
        // --- STORE NOTE DATA IN DOM ---
        div.dataset.raw = textRaw || ""; 
        div.dataset.clean = textClean || "";
        div.dataset.filtered = text || "";
        // Store note title (default: Note X).
        let noteTitle = div.dataset.title || `Note ${historyCounter}`;
        // Use provided timestamp, otherwise current date.
        const dateObj = timestamp ? new Date(timestamp) : new Date();
        // Date + time formatting.
        const dateStr = dateObj.toLocaleDateString('fr-FR', { year: 'numeric', month: '2-digit', day: '2-digit' });
        const timeStr = dateObj.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
        const statusColor = dim > 0 ? 'text-emerald-500' : 'text-amber-500';
        const pinned = isPinned(id);

        // Reuse saved title from localStorage when available.
        const savedTitle = localStorage.getItem(`note_title_${id}`);
        if (savedTitle) noteTitle = savedTitle;
        div.dataset.title = noteTitle;

        div.className = 'history-item fade-in bg-white p-4 rounded-lg border border-slate-200 shadow-sm hover:shadow-md cursor-pointer transition-all duration-200 mb-2 border-l-4 border-l-transparent group relative pr-8';
        div.dataset.search = `${noteTitle} ${text || ''} ${textRaw || ''}`.toLowerCase();

        div.innerHTML = `
            <div class="flex justify-between items-start mb-2">
                <div class="flex items-center gap-3">
                    <input type="checkbox" class="rag-checkbox w-4 h-4 text-brand-600 rounded border-gray-300 focus:ring-brand-500 cursor-pointer" title="Inclure">
                    <div class="flex items-center gap-2">
                        <span class="w-6 h-6 rounded-md bg-slate-100 flex items-center justify-center text-slate-500 text-xs font-bold group-hover:bg-brand-100 group-hover:text-brand-600 transition-colors">#${historyCounter}</span>
                        <input type="text" class="note-title-input text-xs font-semibold text-slate-700 bg-transparent border-none focus:ring-0 focus:outline-none p-0 m-0 w-auto max-w-[120px]" value="${noteTitle}" title="Titre de la note" />
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button class="pin-note-btn text-[10px] px-2 py-1 ${pinned ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-slate-100 text-slate-600 border-slate-200'} rounded border" title="Épingler">★</button>
                    <button class="note-detail-btn text-[10px] px-2 py-1 bg-slate-100 rounded border border-slate-200" title="Détails">!</button>
                    <span class="text-[10px] text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">${dateStr} ${timeStr}</span>
                </div>
            </div>
            <div class="flex items-center gap-2 mt-2 pt-2 border-t border-slate-50">
                <i class="fa-solid fa-database ${statusColor} text-[10px]"></i>
                <span class="text-[10px] text-slate-400">${dim > 0 ? 'Vectorisé' : 'Texte seul'}</span>
            </div>
            <button class="delete-btn absolute top-3 right-3 text-slate-300 hover:text-red-500 transition-colors p-1"><i class="fa-solid fa-trash-can"></i></button>
        `;
        
        // --- EVENTS ---
        const checkbox = div.querySelector('.rag-checkbox');
        checkbox.dataset.role = "rag-checkbox";
        checkbox.dataset.noteId = id;
        checkbox.checked = selectedNoteIds.has(id);
        checkbox.addEventListener('change', () => setNoteSelected(id, checkbox.checked));
        checkbox.addEventListener('click', (e) => e.stopPropagation());

        // Inline title editing inside history item.
        const titleInput = div.querySelector('.note-title-input');
        titleInput.addEventListener('click', e => e.stopPropagation());
        titleInput.addEventListener('change', e => {
            const newTitle = titleInput.value.trim() || `Note ${historyCounter}`;
            div.dataset.title = newTitle;
            localStorage.setItem(`note_title_${id}`, newTitle);
            const cacheItem = notesCache.find(n => getNoteId(n) === id);
            if (cacheItem) cacheItem.title = newTitle;
            // Keep main title input synced for active note.
            if (div.classList.contains('active')) {
                const mainTitleInput = document.getElementById('noteTitleInput');
                if (mainTitleInput) mainTitleInput.value = newTitle;
            }
        });

        // Note click behavior.
        div.onclick = () => {
            // 1. Read note variants from DOM.
            currentFilteredText = div.dataset.filtered;
            currentDirtyText = div.dataset.raw;
            currentCleanText = div.dataset.clean;
            // 2. Reset to default filtered view.
            viewMode = "filtered";
            lastNonDirtyMode = "filtered";
            updateResultView();
            // 3. Highlight selected history item.
            document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
            div.classList.add('active');
            // 4. Scroll output to top.
            resultDiv.parentElement.scrollTo({ top: 0, behavior: 'smooth' });
            // 5. Sync main title input.
            const mainTitleInput = document.getElementById('noteTitleInput');
            if (mainTitleInput) mainTitleInput.value = div.dataset.title || `Note ${historyCounter}`;
        };

        const pinBtn = div.querySelector('.pin-note-btn');
        if (pinBtn) {
            pinBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                togglePinned(id);
            });
        }

        const detailBtn = div.querySelector('.note-detail-btn');
        if (detailBtn) {
            detailBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openDetail({
                    id,
                    text: div.dataset.filtered,
                    text_raw: div.dataset.raw,
                    timestamp,
                    title: div.dataset.title
                });
            });
        }

        // Delete note action.
        div.querySelector('.delete-btn').onclick = async (e) => {
            e.stopPropagation();
            if(!confirm("Supprimer ?")) return;
            try {
                const r = await fetch(`/recordings/${id}`, { method: 'DELETE' });
                if(r.ok) { div.remove(); setNoteSelected(id, false); }
            } catch(err) { alert("Erreur suppression"); }
        };

        ensureNoteInCache({ id, text, text_raw: textRaw, text_clean: textClean, timestamp, title: noteTitle });
        if (options.append) localHistoryList.appendChild(div);
        else localHistoryList.prepend(div);
        updateSelectedCount();
    }

    // ============================================
    // 4. MANUAL RAG (FORMATTED HTML OUTPUT)
    // ============================================
    if(btnLaunchRag) btnLaunchRag.addEventListener('click', launchRagAnalysis);

    async function launchRagAnalysis() {
        if (!currentPatientId) { alert("Aucun patient sélectionné."); return; }
        const selectedIds = Array.from(selectedNoteIds);
        if (selectedIds.length === 0) { alert("Sélectionnez au moins une note."); return; }

        ragPlaceholder.style.display = 'none';
        ragContent.style.display = 'block';
        ragContent.innerHTML = `<div class="flex flex-col items-center justify-center h-full py-8 space-y-3 animate-pulse"><div class="h-2 bg-slate-100 rounded w-3/4"></div><div class="h-2 bg-slate-100 rounded w-1/2"></div><span class="text-xs text-brand-500 font-medium">Analyse en cours...</span></div>`;

        try {
            const resp = await fetch('/rag/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ patient_id: currentPatientId, note_ids: selectedIds })
            });
            if (!resp.ok) throw new Error(await resp.statusText);
            const data = await resp.json();

            if (data.status !== "success") {
                throw new Error(data.message || "Erreur analyse");
            }

            const report = data.data?.medical_report || "Pas de rapport.";
            const diseases = data.data?.validated_diseases || [];
            const recs = data.data?.recommendations || [];
            const warnings = data.data?.global_warnings || [];
            const steps = data.data?.processing_steps || [];

            const formattedReport = report.replace(/\n/g, '<br>');
            const diseaseHtml = diseases.length ? diseases.map(d => `<span class="text-[10px] bg-slate-100 border border-slate-200 rounded px-2 py-0.5">${d}</span>`).join(' ') : '<span class="text-[10px] text-slate-400">Aucune</span>';
            const warningsHtml = warnings.length ? warnings.map(w => `<li>${w}</li>`).join('') : '<li>RAS</li>';

            const recsHtml = recs.length ? recs.map(r => `
                <div class="border border-slate-200 rounded-lg p-3 bg-white">
                    <div class="flex items-center gap-2 mb-2">
                        <div class="bg-brand-100 text-brand-600 p-1.5 rounded-md"><i class="fa-solid fa-pills text-[10px]"></i></div>
                        <div class="text-xs font-bold text-slate-700">${r.name}</div>
                        <span class="ml-auto text-[10px] text-slate-400">${r.posology || 'Voir RCP'}</span>
                    </div>
                    <div class="text-[11px] text-slate-600">
                        <div><span class="font-semibold">Justification:</span> ${r.justification || '—'}</div>
                        <div><span class="font-semibold">Composition:</span> ${(r.composition || []).join(', ') || '—'}</div>
                        <div><span class="font-semibold">Effets indésirables:</span> ${(r.side_effects || []).join('; ') || '—'}</div>
                        <div><span class="font-semibold">Alertes:</span> ${(r.contextual_alerts || []).join('; ') || '—'}</div>
                        <div><span class="font-semibold">Vidal:</span> ${(r.vidal_warnings || []).join('; ') || '—'}</div>
                        ${r.source_url ? `<div><a class="text-brand-600 text-[10px]" href="${r.source_url}" target="_blank">Source Vidal</a></div>` : ''}
                    </div>
                </div>
            `).join('') : '<div class="text-xs text-slate-400">Aucune recommandation.</div>';

            const stepsHtml = steps.length ? steps.map(s => `<li>${s}</li>`).join('') : '<li>Aucun détail.</li>';

            ragContent.innerHTML = `
                <div class="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
                    <div class="flex items-center gap-2 mb-3 pb-2 border-b border-slate-50">
                        <div class="bg-brand-100 text-brand-600 p-1.5 rounded-md"><i class="fa-solid fa-user-doctor text-xs"></i></div>
                        <h4 class="text-xs font-bold text-slate-700">Analyse Prescription</h4>
                        <span class="ml-auto text-[10px] text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full border border-slate-100">${selectedIds.length} notes</span>
                    </div>

                    <div class="mb-3">
                        <div class="text-[11px] font-bold text-slate-600 mb-1">Maladies validées</div>
                        <div class="flex flex-wrap gap-1">${diseaseHtml}</div>
                    </div>

                    <div class="mb-3">
                        <div class="text-[11px] font-bold text-slate-600 mb-1">Recommandations</div>
                        <div class="space-y-2">${recsHtml}</div>
                    </div>

                    <div class="mb-3">
                        <div class="text-[11px] font-bold text-slate-600 mb-1">Alertes globales</div>
                        <ul class="text-[11px] text-slate-600 list-disc pl-4">${warningsHtml}</ul>
                    </div>

                    <div class="mb-3">
                        <div class="text-[11px] font-bold text-slate-600 mb-1">Rapport médical</div>
                        <div class="text-[11px] text-slate-600 leading-relaxed">${formattedReport}</div>
                    </div>

                    <details class="text-[11px] text-slate-500">
                        <summary class="cursor-pointer">Voir les étapes</summary>
                        <ul class="list-disc pl-4 mt-2">${stepsHtml}</ul>
                    </details>

                    <div class="mt-4 pt-3 border-t border-slate-50 flex gap-2">
                        <button onclick="document.getElementById('ragPlaceholder').style.display='flex'; document.getElementById('ragContent').style.display='none';" class="ml-auto text-[10px] text-slate-400 hover:text-slate-600">Fermer</button>
                    </div>
                </div>
            `;
        } catch (e) {
            ragContent.innerHTML = `<div class="p-4 text-center text-red-500 text-xs bg-red-50 rounded border border-red-100">${e.message}<br><button onclick="document.getElementById('ragPlaceholder').style.display='flex'; document.getElementById('ragContent').style.display='none';" class="underline mt-2">Retour</button></div>`;
        }
    }

    // ============================================
    // 5. DATA SUBMISSION (LIVE TRANSCRIPTION -> API)
    // ============================================
    async function sendTextToServer() {
        stopBtn.classList.add('opacity-50', 'cursor-not-allowed');
        visualizer.classList.remove('recording');
        statusDiv.textContent = "Correction & filtrage...";
        setStatusIndicator('processing');

        const rawText = (liveDisplayText || "").trim();
        if (!rawText) {
            statusDiv.textContent = "Texte vide.";
            return;
        }

        try {
            const response = await fetch('/transcribe_text', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    patient_id: currentPatientId,
                    text_raw: rawText,
                    title: (document.getElementById('noteTitleInput')?.value || "Note ")
                })
            });
            if (!response.ok) throw new Error(await response.text());
            const data = await response.json();

            if (liveSessionId) {
                fetch('/draft_text/clear', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        patient_id: currentPatientId,
                        session_id: liveSessionId,
                        text_raw: ""
                    })
                }).catch(() => {});
            }

            currentDirtyText = data.text_raw || "";
            currentCleanText = data.text_clean || "";
            currentFilteredText = data.text_filtered || "";
            viewMode = "filtered";
            lastNonDirtyMode = "filtered";
            updateResultView();

            statusDiv.textContent = "Sauvegardé.";
            addToHistoryUI(data.id, data.text_filtered, data.text_raw, data.text_clean, data.dimension);
            applyHistorySearchFilter();
            lastLoadedRecordings.unshift({
                id: data.id,
                text: data.text_filtered,
                text_raw: data.text_raw,
                text_clean: data.text_clean,
                dimension: data.dimension,
                timestamp: data.timestamp || new Date().toISOString()
            });

        } catch (error) {
            resultDiv.textContent = "Erreur: " + error.message;
        } finally {
            stopBtn.classList.add('hidden');
            stopBtn.classList.remove('flex');
            stopBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            startBtn.classList.remove('hidden');
            setStatusIndicator('ready');
            setTimeout(() => { statusDiv.textContent = "Prêt"; }, 2000);
        }
    }

    async function autosaveLiveDraft() {
        if (!currentPatientId || !liveSessionId) return;
        const text = (liveDisplayText || "").trim();
        if (!text) return;

        try {
            await fetch('/draft_text', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    patient_id: currentPatientId,
                    session_id: liveSessionId,
                    text_raw: text
                })
            });
        } catch (_) { }
    }

    // ============================================
    // 6. RESIZER + PATIENT LOGIC
    // ============================================
    
    // Vertical panel resizer.
    if (dragHandle && topPanel && leftContainer) {
        dragHandle.addEventListener('mousedown', (e) => { isResizing = true; document.body.style.cursor = 'row-resize'; e.preventDefault(); });
        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            const containerRect = leftContainer.getBoundingClientRect();
            const percentage = ((e.clientY - containerRect.top) / containerRect.height) * 100;
            if (percentage > 20 && percentage < 80) topPanel.style.height = `${percentage}%`;
        });
        document.addEventListener('mouseup', () => { isResizing = false; document.body.style.cursor = 'default'; });
    }

    // Selection counter sync.
    function updateSelectionCounter() {
        updateSelectedCount();
        if (selectAllCheckbox) {
            const total = notesCache.length;
            selectAllCheckbox.checked = (total > 0 && selectedNoteIds.size === total);
        }
    }
    if (selectAllCheckbox) selectAllCheckbox.addEventListener('change', (e) => {
        notesCache.forEach(n => setNoteSelected(getNoteId(n), e.target.checked));
        updateSelectionCounter();
    });

    if (filterNotesModal) {
        filterNotesModal.addEventListener('click', (e) => {
            if (e.target === filterNotesModal) {
                filterNotesModal.classList.add('hidden');
                filterNotesModal.classList.remove('flex');
            }
        });
    }

    if (noteDetailModal) {
        noteDetailModal.addEventListener('click', (e) => {
            if (e.target === noteDetailModal) {
                noteDetailModal.classList.add('hidden');
                noteDetailModal.classList.remove('flex');
            }
        });
    }

    // ============================================
    // PATIENTS & DRAWER LOGIC
    // ============================================
    async function loadPatients() {
        try {
            const resp = await fetch('/patients');
            const patients = await resp.json();
            patientsListDiv.innerHTML = '';
            patients.forEach(p => {
                const el = document.createElement('div');
                el.className = `p-3 rounded-lg border cursor-pointer transition flex justify-between items-center ${p.id === currentPatientId ? 'bg-brand-50 border-brand-200' : 'bg-white border-slate-200 hover:border-brand-300'}`;
                el.innerHTML = `<span class="text-sm font-medium text-slate-700">${p.name}</span>`;
                el.onclick = () => selectPatient(p);
                patientsListDiv.appendChild(el);
            });
        } catch (e) { console.error('Erreur chargement patients:', e); }
    }

    function selectPatient(patient) {
        currentPatientId = patient.id;
        if(activePatientName) activePatientName.textContent = patient.name;
        if(docPatientName) docPatientName.textContent = patient.name;
        if(noPatientOverlay) noPatientOverlay.classList.add('hidden');
        toggleDrawer(false);
        loadPatientHistory(patient.id);
        
        // Reset View
        if(resultDiv) resultDiv.innerHTML = '<span class="text-slate-300 italic font-sans">Sélectionnez une note.</span>';
        currentDirtyText = "";
        currentCleanText = "";
        currentFilteredText = "";
        viewMode = "filtered";
        lastNonDirtyMode = "filtered";
        if(ragPlaceholder) ragPlaceholder.style.display = 'flex';
        if(ragContent) ragContent.style.display = 'none';
    }

    async function loadPatientHistory(id) {
        localHistoryList.innerHTML = '';
        historyCounter = 0;
        notesCache.length = 0;
        selectedNoteIds.clear();
        try {
            const resp = await fetch(`/patients/${id}/history`);
            if (resp.ok) {
                const recordings = await resp.json();
                if (recordings.length > 0 && emptyHistoryMsg) emptyHistoryMsg.style.display = 'none';
                lastLoadedRecordings = recordings;
                renderHistoryList(recordings);
            }
        } catch (e) { console.error(e); }
    }

    function renderHistoryList(recordings) {
        localHistoryList.innerHTML = '';
        historyCounter = 0;
        notesCache.length = 0;

        const pinned = [];
        const others = [];
        recordings.forEach(rec => {
            if (isPinned(rec.id)) pinned.push(rec);
            else others.push(rec);
        });

        const sortByDateDesc = (a, b) => {
            const da = a.timestamp ? new Date(a.timestamp).getTime() : 0;
            const db = b.timestamp ? new Date(b.timestamp).getTime() : 0;
            return db - da;
        };

        pinned.sort(sortByDateDesc);
        others.sort(sortByDateDesc);

        if (pinned.length) {
            const pinHeader = document.createElement('div');
            pinHeader.className = 'text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 inline-block mb-2';
            pinHeader.textContent = 'Épinglées';
            localHistoryList.appendChild(pinHeader);
            pinned.forEach(rec => addToHistoryUI(rec.id, rec.text, rec.text_raw, rec.text_clean, rec.dimension, rec.timestamp, { append: true }));
        }

        let lastGroup = '';
        others.forEach(rec => {
            const d = rec.timestamp ? new Date(rec.timestamp) : null;
            const group = d ? d.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' }) : 'Date inconnue';
            if (group !== lastGroup) {
                const sep = document.createElement('div');
                sep.className = 'text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-3 mb-1';
                sep.textContent = group;
                localHistoryList.appendChild(sep);
                lastGroup = group;
            }
            addToHistoryUI(rec.id, rec.text, rec.text_raw, rec.text_clean, rec.dimension, rec.timestamp, { append: true });
        });

        applyHistorySearchFilter();
        updateSelectionCounter();
    }

    // Drawer Logic
    function toggleDrawer(show) {
        if (show) { 
            overlay.classList.remove('hidden'); 
            setTimeout(() => overlay.classList.remove('opacity-0'), 10); 
            drawer.classList.remove('drawer-closed'); 
            drawer.classList.add('drawer-open'); 
            loadPatients();
        }
        else { 
            overlay.classList.add('opacity-0'); 
            drawer.classList.remove('drawer-open'); 
            drawer.classList.add('drawer-closed'); 
            setTimeout(() => overlay.classList.add('hidden'), 300); 
        }
    }
    if(openDrawerBtn) openDrawerBtn.addEventListener('click', () => toggleDrawer(true));
    if(closeDrawerBtn) closeDrawerBtn.addEventListener('click', () => toggleDrawer(false));
    if(overlay) overlay.addEventListener('click', () => toggleDrawer(false));

    // Speech Recognition (Live)
    function setupRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            alert("Votre navigateur ne supporte pas la dictée en temps réel.");
            return null;
        }

        const recog = new SpeechRecognition();
        recog.lang = 'fr-FR';
        recog.interimResults = true;
        recog.continuous = true;

        recog.onresult = (event) => {
            let interim = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    liveFinalText += transcript + " ";
                } else {
                    interim += transcript;
                }
            }
            liveInterimText = interim;
            liveDisplayText = `${liveFinalText} ${liveInterimText}`.trim();

            currentDirtyText = liveDisplayText;
            viewMode = "dirty";
            updateResultView();
        };

        recog.onerror = () => {
            statusDiv.textContent = "Erreur de dictée.";
            setStatusIndicator('idle');
        };

        recog.onend = () => {
            isRecognizing = false;
            if (pendingSendAfterStop) {
                pendingSendAfterStop = false;
                sendTextToServer();
                return;
            }
            if (!manualStopRequested) {
                setTimeout(() => {
                    try {
                        recognition.start();
                        isRecognizing = true;
                    } catch (_) {
                        statusDiv.textContent = "Redémarrage dictée impossible.";
                    }
                }, 200);
            }
        };

        return recog;
    }

    if (startBtn) {
        startBtn.addEventListener('click', async () => {
            if (!currentPatientId) { toggleDrawer(true); return; }
            statusDiv.textContent = "Initialisation...";

            if (!recognition) recognition = setupRecognition();
            if (!recognition) return;

            liveFinalText = "";
            liveInterimText = "";
            liveDisplayText = "";
            currentDirtyText = "";
            manualStopRequested = false;
            liveSessionId = (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now());

            startBtn.classList.add('hidden');
            stopBtn.classList.remove('hidden');
            stopBtn.classList.add('flex');
            visualizer.classList.add('recording');
            visualizer.classList.remove('opacity-50');
            statusDiv.innerHTML = '<span class="text-red-500 font-bold animate-pulse">● Dictée live...</span>';
            setStatusIndicator('listening');
            resultDiv.innerHTML = '<span class="text-slate-400 italic">Écoute active...</span>';

            isRecognizing = true;
            recognition.start();

            if (autosaveTimer) clearInterval(autosaveTimer);
            autosaveTimer = setInterval(autosaveLiveDraft, AUTOSAVE_MS);
        });
    }

    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            manualStopRequested = true;
            if (autosaveTimer) clearInterval(autosaveTimer);
            autosaveTimer = null;
            if (recognition && isRecognizing) {
                pendingSendAfterStop = true;
                recognition.stop();
            }
        });
    }

    setStatusIndicator('ready');
});