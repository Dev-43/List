console.log("Script loaded!");

const searchInput =document.querySelector("#search-input");
const searchButton =document.querySelector("#search-button");
const resultsContainer=document.querySelector("#result-container")
searchButton.addEventListener("click", function() {
    const query=searchInput.value;

    resultsContainer.innerHTML='<h2>Search Results</h2>';
    
    const resultCard=document.createElement('div');
    resultCard.classList.add('result-card');
    resultCard.textContent=`
    <p class="result-title">${query}</p>;
    <button class="add-btn">Add to List</button>`;

    resultsContainer.appendChild(resultCard);

});