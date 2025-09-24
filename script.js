console.log("Script loaded!");

const searchInput =document.querySelector("#search-input");
const searchButton =document.querySelector("#search-button");
const resultsContainer=document.querySelector("#result-container")
searchButton.addEventListener("click", function() {
    const query=searchInput.value;

    resultsContainer.innerHTML='<h2>Search Results</h2>';
    
    const resultCard=document.createElement('div');
    resultCard.classList.add('result-card');
    resultCard.innerHTML=`
    <p class="result-title">${query}</p>
    <button class="add-btn">Add to List</button>`;

    resultsContainer.appendChild(resultCard);
});

resultsContainer.addEventListener("click",function(event){

    if(event.target.classList.contains("add-btn")){
        console.log("Add Button Clicked!");
    }

    const clickedButton=event.target;
    clickedButton.textContent='Added!';
    clickedButton.disabled=true;

    clickedButton.classList.remove("add-btn");
    clickedButton.classList.add("added-btn");

    console.log("Item Added!");
}
)