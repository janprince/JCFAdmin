document.addEventListener("DOMContentLoaded",function(){var e=document.getElementById("show-hide-column");if(e){let t=new DataTable(e,{responsive:!0,dom:"<'d-md-flex justify-content-between align-items-center mt-2 mb-3'<'columnToggleWrapper'B>f>rt<'d-md-flex justify-content-between align-items-center mt-2'lp>",language:{paginate:{first:'<svg  xmlns="http://www.w3.org/2000/svg"  width="24"  height="24"  viewBox="0 0 24 24"  fill="none"  stroke="currentColor"  stroke-width="2"  stroke-linecap="round"  stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M11 7l-5 5l5 5" /><path d="M17 7l-5 5l5 5" /></svg>',previous:'<svg  xmlns="http://www.w3.org/2000/svg"  width="24"  height="24"  viewBox="0 0 24 24"  fill="none"  stroke="currentColor"  stroke-width="2"  stroke-linecap="round"  stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M15 6l-6 6l6 6" /></svg>',next:'<svg  xmlns="http://www.w3.org/2000/svg"  width="24"  height="24"  viewBox="0 0 24 24"  fill="none"  stroke="currentColor"  stroke-width="2"  stroke-linecap="round"  stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M9 6l6 6l-6 6" /></svg>',last:'<svg  xmlns="http://www.w3.org/2000/svg"  width="24"  height="24"  viewBox="0 0 24 24"  fill="none"  stroke="currentColor"  stroke-width="2"  stroke-linecap="round"  stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M7 7l5 5l-5 5" /><path d="M13 7l5 5l-5 5" /></svg>'}}});var o,e=["Company","Symbol","Price","Change","Volume","Market Cap","Rating","Status"],n=document.querySelector(".columnToggleWrapper");n?((o=document.createElement("div")).className="dropdown",o.innerHTML=`
        <button class="btn btn-sm btn-secondary" type="button" data-bs-toggle="dropdown" data-bs-auto-close="outside">
            Show/Hide Columns
        </button>
        <ul class="dropdown-menu" id="columnToggleMenu">
            ${e.map((e,o)=>`
                <li class="dropdown-item">
                    <div class="form-check">
                        <input class="form-check-input form-check-input-light fs-14 mt-0 toggle-vis" 
                               type="checkbox" data-column="${o}" id="colToggle${o}" checked>
                        <label class="form-check-label fw-medium" for="colToggle${o}">
                            ${e}
                        </label>
                    </div>
                </li>
            `).join("")}
        </ul>
    `,n.appendChild(o),(e=document.getElementById("columnToggleMenu"))?e.addEventListener("change",function(e){var o;e.target.classList.contains("toggle-vis")&&(o=parseInt(e.target.dataset.column,10),(o=t.column(o))?o.visible(e.target.checked):console.error("Datatables Show Hide Columns: Column not found."))}):console.error("Datatables Show Hide Columns: Column toggle menu not found.")):console.error("Datatables Show Hide Columns: Column toggle wrapper not found.")}});