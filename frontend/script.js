(function(){
  const menuBtn = document.getElementById("menuBtn");
  const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.getElementById("toggleBtn");

  if(menuBtn){
    menuBtn.addEventListener("click", ()=>{
      sidebar.classList.toggle("collapsed");
    });
  }
  if(toggleBtn){
    toggleBtn.addEventListener("click", ()=>{
      const collapsed = sidebar.classList.toggle("collapsed");
      toggleBtn.textContent = collapsed ? "Expand" : "Collapse";
    });
  }
})();
