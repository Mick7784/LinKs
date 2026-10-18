"use strict";
// Callers own routing and data loading; this helper only selects DOM views.
window.StudioNavigation={activate(id,views,buttons){
 for(const view of views)view.classList.toggle("active",view.id===id);
 for(const button of buttons){const active=button.dataset.tab===id;button.classList.toggle("active",active);if(active)button.setAttribute("aria-current","page");else button.removeAttribute("aria-current")}
}};
