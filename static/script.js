document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const searchInput = document.getElementById('searchInput');
    const studentGrid = document.getElementById('studentGrid');
    const loadingState = document.getElementById('loading');
    const noResultsState = document.getElementById('noResults');
    const statsBar = document.getElementById('statsBar');
    const countSpan = document.getElementById('count');
    const filterChips = document.querySelectorAll('.filter-chip');

    // Toast Container
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    document.body.appendChild(toastContainer);

    // Modal Elements
    const modal = document.getElementById('exitModal');
    const closeModalBtn = document.getElementById('closeModal');
    const cancelBtn = document.getElementById('cancelBtn');
    const saveBtn = document.getElementById('saveBtn');
    const exitForm = document.getElementById('exitForm');
    const logoutBtn = document.getElementById('logoutBtn');

    // New Form Elements
    const checkVuelve = document.getElementById('checkVuelve');
    const hoursContainer = document.getElementById('hoursContainer');


    // State
    let allStudents = [];
    let currentFilter = 'all';
    let selectedStudent = null;
    let csrfToken = null;

    // Fetch CSRF Token
    async function refreshCsrfToken() {
        try {
            const res = await fetch('/api/csrf-token');
            const data = await res.json();
            window.csrfToken = data.csrf_token;
            csrfToken = data.csrf_token;
        } catch (e) {
            console.error("Failed to fetch CSRF token");
        }
    }

    // Constants
    const DATA_URL = '/data/students.json';
    const API_URL = '/api/exit'; // Relative path to support any port

    // Initialize
    refreshCsrfToken();
    fetchData();

    // Check for correct protocol
    if (window.location.protocol === 'file:') {
        showToast('ADVERTENCIA CRÍTICA: Estás abriendo "index.html" directamente como archivo. Usa el servidor para que funcione.', 'error');
    }

    // Event Listeners with Debounce
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            handleSearch(e.target.value);
        }, 300);
    });

    filterChips.forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelector('.filter-chip.active').classList.remove('active');
            chip.classList.add('active');
            currentFilter = chip.dataset.filter;
            handleSearch(searchInput.value);
        });
    });

    // Modal Listeners
    closeModalBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    saveBtn.addEventListener('click', saveExit);
    if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);

    // Close modal on click outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });


    // Dynamic Accompanied Logic
    const accompaniedRadios = document.getElementsByName('accompaniedBy');
    accompaniedRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            // Logic to show/hide specific tutor details if needed, for now just collecting value
        });
    });

    // Toggle Hours Logic
    checkVuelve.addEventListener('change', (e) => {
        if (e.target.checked) {
            hoursContainer.classList.remove('hidden');
        } else {
            hoursContainer.classList.add('hidden');
        }
    });

    async function fetchData() {
        try {
            const response = await fetch(DATA_URL);
            if (response.status === 401 || response.type === 'opaqueredirect' || response.url.includes('login.html')) {
                window.location.href = '/login.html';
                return;
            }
            if (!response.ok) throw new Error('Network response was not ok');
            allStudents = await response.json();
            loadingState.classList.add('hidden');
            renderStudents(allStudents.slice(0, 50));
            updateStats(allStudents.length);
            statsBar.classList.remove('hidden');
        } catch (error) {
            console.error('Error fetching data:', error);
            // Check if parsing failed (likely got HTML login page instead of JSON)
            if (error.name === 'SyntaxError') {
                window.location.href = '/login.html';
                return;
            }
            loadingState.innerHTML = '<p>Error al cargar los datos. Por favor, recarga la página.</p>';
        }
    }

    function handleSearch(query) {
        const rawTerm = query.toLowerCase().trim();
        if (rawTerm === '') {
            renderStudents(allStudents.slice(0, 50));
            updateStats(allStudents.length);
            noResultsState.classList.add('hidden');
            return;
        }

        const terms = rawTerm.split(/\s+/).filter(t => t.length > 0);

        const filtered = allStudents.filter(student => {
            const name = (student.name || '').toLowerCase();
            const group = (student.group || '').toLowerCase();
            const dni = (student.dni || '').toLowerCase();

            // Check if ALL terms are present in at least one of the fields combined
            // Or better: Check if ALL terms match ANY of the fields? 
            // Usually "Marc Garcia" -> "Marc" in Name AND "Garcia" in Name.
            // But if I type "Marc B_2D", I want "Marc" in Name AND "B_2D" in Group.
            // Simplest robust way: Combine all searchable text and check if all terms exist in it.

            const searchableText = `${name} ${group} ${dni}`;
            return terms.every(term => searchableText.includes(term));
        });

        renderStudents(filtered);
        updateStats(filtered.length);

        if (filtered.length === 0) {
            noResultsState.classList.remove('hidden');
            // Suggestion logic could go here
        } else {
            noResultsState.classList.add('hidden');
        }
    }

    function updateStats(count) {
        if (!countSpan || !statsBar) return;
        countSpan.textContent = count;
        if (count > 0 && count < allStudents.length) {
            statsBar.classList.remove('hidden');
        } else {
            statsBar.classList.add('hidden');
        }
    }

    function renderStudents(students) {
        studentGrid.innerHTML = '';
        const studentsToRender = students.slice(0, 100);
        studentsToRender.forEach(student => {
            const card = createStudentCard(student);
            studentGrid.appendChild(card);
        });
    }

    function createStudentCard(student) {
        const card = document.createElement('div');
        card.className = 'student-card';

        const name = student.name || 'Sin Nombre';
        const group = student.group || 'Sin Grupo';
        const dni = student.dni || '---';
        const t1 = student.tutor1 || {};
        const t2 = student.tutor2 || {};

        card.innerHTML = `
            <div class="card-header">
                <div class="student-photo-container">
                    <img src="${(student.photo && student.photo.startsWith('http')) ? student.photo : (student.photo ? (student.photo.startsWith('/') ? student.photo : '/' + student.photo) : '/data/logo.gif')}" 
                         alt="${name}" 
                         onerror="console.warn('Fallo al cargar foto de:', '${name}', 'Source:', this.src); this.src='/data/logo.gif'; this.classList.add('is-placeholder')"
                         class="student-photo ${!student.photo ? 'is-placeholder' : ''}">
                </div>
                <div class="student-info-header">
                    <div class="student-name">${name}</div>
                    <div class="dni-tiny">${dni}</div>
                </div>
                <div class="group-badge">${group}</div>
            </div>
            
            <div id="recurrence-${student.id}" class="recurrence-alert hidden">
                <i class="ph-fill ph-warning-octagon"></i> Reincidente este mes
            </div>
            
            <div class="card-body">
                <div class="info-row">
                    <i class="ph-fill ph-identification-card"></i>
                    <span class="info-label">DNI</span>
                    <span class="info-value dni-value">${dni}</span>
                </div>

                <!-- Phone List -->
                <div class="phones-section">
                    ${(student.phones || []).map(p => `
                        <a href="tel:${p.number}" class="phone-chip ${p.urgent ? 'urgent' : ''}">
                            <i class="ph-fill ph-phone"></i>
                            <div class="phone-data">
                                <span class="phone-label">${p.label}</span>
                                <span class="phone-number">${p.number}</span>
                            </div>
                        </a>
                    `).join('')}
                    ${(!student.phones || student.phones.length === 0) ? '<div class="no-phones">Sin teléfonos</div>' : ''}
                </div>

                ${t1.name ? `
                <div class="tutor-box">
                    <div class="tutor-label">Tutor 1</div>
                    <div class="tutor-name">${t1.name}</div>
                    <div class="tutor-dni">${t1.dni || 'No DNI'}</div>
                </div>` : ''}
                
                ${t2.name ? `
                <div class="tutor-box">
                    <div class="tutor-label">Tutor 2</div>
                    <div class="tutor-name">${t2.name}</div>
                    <div class="tutor-dni">${t2.dni || 'No DNI'}</div>
                </div>` : ''}
            </div>

            <div class="card-actions">
                <button class="btn-exit" onclick="openExitModal('${student.id}')">
                    <i class="ph-bold ph-door-open"></i> Registrar Salida
                </button>
            </div>
            
            <div class="exit-counter-badge" id="counter-${student.id}">
                <i class="ph-bold ph-calendar-check"></i>
                <span class="count-val">...</span>
            </div>
        `;

        // Update exit count asynchronously
        updateExitCount(student.id, card.querySelector('.count-val'));

        // Bind the click event correctly since inline onclick handles string limitation
        const btn = card.querySelector('.btn-exit');
        btn.onclick = () => openExitModal(student); // Pass full object

        return card;
    }

    async function updateExitCount(studentId, element) {
        try {
            const res = await fetch(`/api/student-history?id=${studentId}`);
            if (res.ok) {
                const data = await res.json();
                element.textContent = data.count || 0;

                if (data.count > 0) {
                    element.parentElement.classList.add('has-exits');
                }

                // Recurrence Alert logic (Feature 6)
                if (data.monthlyCount >= 3) {
                    const alertElem = document.getElementById(`recurrence-${studentId}`);
                    if (alertElem) alertElem.classList.remove('hidden');
                }
            }
        } catch (e) {
            element.textContent = '0';
        }
    }

    // Modal Elements & Functions
    const printBtn = document.getElementById('printBtn');

    window.openExitModal = function (student) {
        selectedStudent = student;
        modal.classList.remove('hidden');

        document.getElementById('studentNameModal').textContent = student.name;
        document.getElementById('studentGroupModal').textContent = student.group || '';

        const modalPhoto = document.getElementById('studentPhotoModal');
        if (student.photo) {
            modalPhoto.src = student.photo;
            modalPhoto.classList.remove('is-placeholder');
        } else {
            modalPhoto.src = 'data/logo.gif';
            modalPhoto.classList.add('is-placeholder');
        }

        // Update Tutor Labels in the Radio Group
        const t1 = student.tutor1?.name;
        const t2 = student.tutor2?.name;

        const labelT1 = document.getElementById('labelTutor1');
        const labelT2 = document.getElementById('labelTutor2');
        const cardT1 = document.getElementById('cardTutor1');
        const cardT2 = document.getElementById('cardTutor2');

        if (t1) {
            labelT1.textContent = t1.split(' ').slice(0, 2).join(' ');
            cardT1.style.display = 'flex';
        } else {
            cardT1.style.display = 'none';
        }

        if (t2) {
            labelT2.textContent = t2.split(' ').slice(0, 2).join(' ');
            cardT2.style.display = 'flex';
        } else {
            cardT2.style.display = 'none';
        }

        // Reset form
        document.getElementById('motive').value = 'Personal';
        document.querySelector('input[name="accompaniedBy"][value="Solo"]').checked = true;
        checkVuelve.checked = false;
        hoursContainer.classList.add('hidden');
        document.querySelectorAll('input[name="period"]').forEach(cb => cb.checked = false);

        saveBtn.classList.remove('hidden');
        printBtn.classList.add('hidden');
    }

    function closeModal() {
        modal.classList.add('hidden');
        selectedStudent = null;
    }

    printBtn.addEventListener('click', () => {
        window.print();
    });

    async function saveExit() {
        try {
            if (!selectedStudent) {
                showToast('Error: No se ha seleccionado ningún alumno.', 'error');
                return;
            }

            const periodCheckboxes = document.querySelectorAll('input[name="period"]:checked');
            const selectedPeriods = Array.from(periodCheckboxes).map(cb => cb.value);
            const vuelve = checkVuelve.checked;
            const horas = vuelve ? (selectedPeriods.length > 0 ? selectedPeriods.join(', ') : 'No especificado') : '';

            const motiveElem = document.getElementById('motive');
            const motive = motiveElem.value;

            const accompaniedRadio = document.querySelector('input[name="accompaniedBy"]:checked');
            const accompaniedVal = accompaniedRadio.value;

            let tutorName = '';
            if (accompaniedVal === 'Tutor1') tutorName = selectedStudent.tutor1?.name || 'Error';
            else if (accompaniedVal === 'Tutor2') tutorName = selectedStudent.tutor2?.name || 'Error';
            else if (accompaniedVal === 'Otro') tutorName = 'Otro Autorizado';
            else tutorName = '---';

            const payload = {
                studentId: selectedStudent.id,
                studentName: selectedStudent.name,
                group: selectedStudent.group,
                dni: selectedStudent.dni,
                motive: motive,
                accompaniedBy: accompaniedVal,
                tutorName: tutorName,
                vuelve: vuelve,
                horas: horas
            };

            saveBtn.textContent = 'Guardando...';
            saveBtn.disabled = true;

            if (!csrfToken) await refreshCsrfToken();
            const res = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const now = new Date();
                document.getElementById('ticketDate').textContent = now.toLocaleDateString('es-ES');
                document.getElementById('ticketTime').textContent = now.toLocaleTimeString('es-ES');
                document.getElementById('ticketStudent').textContent = selectedStudent.name;
                document.getElementById('ticketGroup').textContent = selectedStudent.group;
                document.getElementById('ticketDNI').textContent = selectedStudent.dni;
                document.getElementById('ticketMotive').textContent = motive;

                let accompDisplay = accompaniedVal;
                if (accompaniedVal === 'Tutor1' || accompaniedVal === 'Tutor2') accompDisplay = tutorName;
                document.getElementById('ticketAccompanied').textContent = accompDisplay;

                const existingReturnInfo = document.getElementById('ticketReturnInfo');
                if (existingReturnInfo) existingReturnInfo.remove();

                if (vuelve) {
                    const ticketAccompanied = document.getElementById('ticketAccompanied');
                    if (ticketAccompanied) {
                        const returnDiv = document.createElement('div');
                        returnDiv.id = 'ticketReturnInfo';
                        returnDiv.className = 'ticket-row';
                        returnDiv.innerHTML = `<br><strong>Regreso:</strong> SÍ - Horas: ${horas}`;
                        ticketAccompanied.parentNode.after(returnDiv);
                    }
                }

                saveBtn.classList.add('hidden');
                printBtn.classList.remove('hidden');
                showToast('Salida registrada correctamente. Ya puedes imprimir el ticket.', 'success');

                // Refresh the list to update counters
                handleSearch(searchInput.value);

            } else {
                const errorData = await res.json().catch(() => ({}));
                const errorMsg = errorData.error || `Error del servidor (${res.status})`;
                showToast('Error al guardar: ' + errorMsg, 'error');
            }

        } catch (e) {
            console.error('Exception during save:', e);
            showToast('Error de conexión o JS.', 'error');
        } finally {
            saveBtn.disabled = false;
            if (printBtn.classList.contains('hidden')) {
                saveBtn.textContent = 'Grabar Salida';
            }
        }
    }

    // History Logic
    const historyBtn = document.getElementById('historyBtn');
    const historyModal = document.getElementById('historyModal');
    const closeHistoryBtn = document.getElementById('closeHistoryBtn');
    const historyTableBody = document.getElementById('historyTableBody');
    const historySearchInput = document.getElementById('historySearchInput');
    const exportBtn = document.getElementById('exportBtn');
    const motiveFilter = document.getElementById('historyMotiveFilter');
    const dateFrom = document.getElementById('historyDateFrom');
    const dateTo = document.getElementById('historyDateTo');
    const clearFiltersBtn = document.getElementById('clearHistoryFilters');

    let allHistoryRecords = [];

    if (historyBtn) historyBtn.addEventListener('click', openHistory);
    if (closeHistoryBtn) closeHistoryBtn.addEventListener('click', () => historyModal.classList.add('hidden'));

    historyModal.addEventListener('click', (e) => {
        if (e.target === historyModal) historyModal.classList.add('hidden');
    });

    if (historySearchInput) historySearchInput.addEventListener('input', () => applyHistoryFilters());
    if (motiveFilter) motiveFilter.addEventListener('change', () => applyHistoryFilters());
    if (dateFrom) dateFrom.addEventListener('change', () => applyHistoryFilters());
    if (dateTo) dateTo.addEventListener('change', () => applyHistoryFilters());
    if (clearFiltersBtn) clearFiltersBtn.addEventListener('click', () => {
        historySearchInput.value = '';
        motiveFilter.value = 'all';
        dateFrom.value = '';
        dateTo.value = '';
        applyHistoryFilters();
    });

    // Upload Logic
    const uploadBtn = document.getElementById('uploadBtn');
    const studentExcelInput = document.getElementById('studentExcelInput');

    if (uploadBtn) {
        uploadBtn.addEventListener('click', () => {
            studentExcelInput.click();
        });
    }

    if (studentExcelInput) {
        studentExcelInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                uploadFile(e.target.files[0]);
            }
        });
    }

    async function uploadFile(file) {
        if (!confirm(`¿Estás seguro de que quieres actualizar la base de datos con el archivo "${file.name}"? Esto sobrescribirá los datos actuales.`)) {
            studentExcelInput.value = '';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="ph-bold ph-spinner ph-spin"></i> Subiendo...';

        try {
            if (!csrfToken) await refreshCsrfToken();
            const res = await fetch('/api/upload-students', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            });

            if (res.ok) {
                const data = await res.json();
                showToast(`Se han actualizado ${data.count} alumnos correctamente.`, 'success');
                fetchData();
            } else {
                const data = await res.json();
                showToast('Error: ' + (data.error || 'No se pudo procesar el archivo'), 'error');
            }
        } catch (error) {
            console.error(error);
            showToast('Error de conexión al subir el archivo.', 'error');
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="ph-bold ph-upload-simple"></i> Actualizar Alumnos';
            studentExcelInput.value = '';
        }
    }

    if (exportBtn) exportBtn.addEventListener('click', exportHistoryToCSV);

    async function openHistory() {
        historyModal.classList.remove('hidden');
        historyTableBody.innerHTML = '<tr><td colspan="9" style="text-align:center">Cargando...</td></tr>';
        try {
            const res = await fetch('/api/history');
            if (!res.ok) throw new Error('Error al cargar historial');
            allHistoryRecords = await res.json();
            renderHistory(allHistoryRecords);
        } catch (e) {
            console.error(e);
            historyTableBody.innerHTML = '<tr><td colspan="9" style="text-align:center; color: #ef4444;">Error de conexión</td></tr>';
        }
    }

    function renderHistory(records) {
        updateHistoryStats(records);
        historyTableBody.innerHTML = '';
        if (records.length === 0) {
            historyTableBody.innerHTML = '<tr><td colspan="9" style="text-align:center">No hay registros</td></tr>';
            return;
        }

        records.forEach(row => {
            const tr = document.createElement('tr');
            const pdfFile = row['PDF'] || '';
            const vuelve = row['Vuelve'] || '-';
            const horas = row['Horas'] ? `${row['Horas']}` : '-';

            tr.innerHTML = `
                <td>${row['Fecha'] || '-'}</td>
                <td>${row['Hora'] || '-'}</td>
                <td>${row['Nombre'] || '-'}</td>
                <td><span class="group-badge small">${row['Grupo'] || '-'}</span></td>
                <td>${row['Motivo'] || '-'}</td>
                <td>${row['Detalle Acompañante'] || row['Acompañante'] || '-'}</td>
                <td>${vuelve === 'Sí' ? `<span style="color:#d8b4fe">Sí (${horas})</span>` : 'No'}</td>
                <td>
                    ${pdfFile ? `<a href="/pdfs/${pdfFile}" target="_blank" class="pdf-link"><i class="ph-bold ph-file-pdf"></i> PDF</a>` : '-'}
                </td>
                <td class="row-actions">
                </td>
            `;

            if (pdfFile) {
                const btn = document.createElement('button');
                btn.className = 'btn-icon-small delete-btn';
                btn.innerHTML = '<i class="ph ph-trash"></i>';
                btn.title = 'Eliminar registro';
                btn.onclick = () => window.deleteRecord(pdfFile);
                tr.querySelector('.row-actions').appendChild(btn);
            } else {
                tr.querySelector('.row-actions').textContent = '-';
            }

            historyTableBody.appendChild(tr);
        });
    }

    function applyHistoryFilters() {
        const term = historySearchInput.value.toLowerCase().trim();
        const motive = motiveFilter.value;
        const from = dateFrom.value;
        const to = dateTo.value;

        const filtered = allHistoryRecords.filter(row => {
            // Search term (DNI, Name, Group)
            const searchable = `${row['Nombre']} ${row['Grupo']} ${row['DNI Alumno']} ${row['ID Alumno']}`.toLowerCase();
            const matchesTerm = !term || searchable.includes(term);

            // Motive
            const matchesMotive = motive === 'all' || row['Motivo'] === motive;

            // Date range
            const rowDate = row['Fecha']; // YYYY-MM-DD
            const matchesFrom = !from || rowDate >= from;
            const matchesTo = !to || rowDate <= to;

            return matchesTerm && matchesMotive && matchesFrom && matchesTo;
        });

        renderHistory(filtered);
    }

    function updateHistoryStats(records) {
        const now = new Date();
        const todayStr = now.toISOString().split('T')[0];

        // Start of week (Monday)
        const tempDate = new Date();
        const day = tempDate.getDay();
        const diff = tempDate.getDate() - day + (day === 0 ? -6 : 1);
        const startOfWeek = new Date(tempDate.setDate(diff));
        startOfWeek.setHours(0, 0, 0, 0);

        const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);

        let todayCount = 0;
        let weekCount = 0;
        let monthCount = 0;

        // Data for trends (Feature 5)
        const dayCounts = { 'Lun': 0, 'Mar': 0, 'Mié': 0, 'Jue': 0, 'Vie': 0 };
        const hourCounts = { '1ª': 0, '2ª': 0, '3ª': 0, 'Recreo': 0, '4ª': 0, '5ª': 0, '6ª': 0 };

        records.forEach(row => {
            if (!row['Fecha']) return;
            const rowDate = new Date(row['Fecha']);

            // Stats
            if (row['Fecha'] === todayStr) todayCount++;
            if (rowDate >= startOfWeek) weekCount++;
            if (rowDate >= startOfMonth) monthCount++;

            // Trends mapping
            const dayIdx = rowDate.getDay(); // 0=Sun, 1=Mon...
            const dayNames = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
            if (dayCounts[dayNames[dayIdx]] !== undefined) dayCounts[dayNames[dayIdx]]++;

            const time = row['Hora'] || '';
            let session = '';
            if (time >= '08:00' && time < '09:25') session = '1ª';
            else if (time >= '09:25' && time < '10:20') session = '2ª';
            else if (time >= '10:20' && time < '11:15') session = '3ª';
            else if (time >= '11:15' && time < '11:45') session = 'Recreo';
            else if (time >= '11:45' && time < '12:40') session = '4ª';
            else if (time >= '12:40' && time < '13:35') session = '5ª';
            else if (time >= '13:35' && time < '14:30') session = '6ª';

            if (session && hourCounts[session] !== undefined) hourCounts[session]++;
        });

        document.getElementById('histStatToday').textContent = todayCount;
        document.getElementById('histStatWeek').textContent = weekCount;
        document.getElementById('histStatMonth').textContent = monthCount;
        document.getElementById('histStatTotal').textContent = records.length;

        // Render Charts
        const trends = document.getElementById('trendsSection');
        if (records.length > 0) {
            trends.classList.remove('hidden');
            renderBarChart('daysChart', dayCounts);
            renderBarChart('hoursChart', hourCounts);
        } else {
            trends.classList.add('hidden');
        }
    }

    function renderBarChart(containerId, data) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const values = Object.values(data);
        const max = Math.max(...values, 1);

        container.innerHTML = Object.entries(data).map(([label, val]) => {
            const height = (val / max) * 100;
            return `
                <div style="flex: 1; display: flex; flex-direction: column; height: 100%;">
                    <div class="chart-bar" style="height: ${height}%;" data-value="${val}"></div>
                    <div class="chart-label">${label}</div>
                </div>
            `;
        }).join('');
    }

    function exportHistoryToCSV() {
        if (!allHistoryRecords || allHistoryRecords.length === 0) return;
        const term = historySearchInput ? historySearchInput.value.toLowerCase().trim() : '';
        let dataToExport = term ? allHistoryRecords.filter(row => {
            const name = (row['Nombre'] || '').toLowerCase();
            const group = (row['Grupo'] || '').toLowerCase();
            const dni = (row['DNI Alumno'] || '').toLowerCase();
            return name.includes(term) || group.includes(term) || dni.includes(term);
        }) : allHistoryRecords;

        const headers = Object.keys(dataToExport[0]);
        const csvRows = [headers.join(',')];
        for (const row of dataToExport) {
            csvRows.push(headers.map(header => `"${('' + (row[header] || '')).replace(/"/g, '""')}"`).join(','));
        }
        const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', `historial_salidas_${new Date().toISOString().slice(0, 10)}.csv`);
        link.click();
    }

    window.deleteRecord = async function (pdfFilename) {
        if (!confirm('¿Estás seguro de eliminar este registro?')) return;
        if (!csrfToken) await refreshCsrfToken();
        try {
            const res = await fetch(`/api/history/${pdfFilename}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': csrfToken
                }
            });
            if (res.ok) {
                openHistory();
                showToast('Registro eliminado.', 'success');
            } else {
                const errorData = await res.json().catch(() => ({}));
                const errorMsg = errorData.error || `Error ${res.status}`;
                showToast(`No se pudo eliminar: ${errorMsg}`, 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Error al conectar con el servidor.', 'error');
        }
    }

    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const icons = {
            success: 'ph-fill ph-check-circle',
            error: 'ph-fill ph-x-circle',
            warning: 'ph-fill ph-warning-circle'
        };

        toast.innerHTML = `
            <i class="${icons[type] || icons.success} toast-icon"></i>
            <span class="toast-message">${message}</span>
        `;

        toastContainer.appendChild(toast);

        // Auto remove
        setTimeout(() => {
            toast.classList.add('removing');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    async function handleLogout() {
        if (!confirm('¿Seguro que quieres cerrar la sesión?')) return;
        try {
            const res = await fetch('/api/logout', {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken }
            });
            if (res.ok) {
                window.location.href = '/login.html';
            } else {
                window.location.href = '/login.html';
            }
        } catch (e) {
            console.error(e);
            window.location.href = '/login.html';
        }
    }

});
