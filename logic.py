function main() {
  var amountMap = constructAmountMap();
  var quantityMap = constructQuantityMap();
  var categoryMap = constructCategoryMap();
  var styleCountMap = countNoOfItems();
  myFunction(amountMap, quantityMap, categoryMap, styleCountMap);
}

function myFunction(amountMap, quantityMap, categoryMap, styleCountMap) {
  var main = SpreadsheetApp.getActive().getSheetByName("Output");
  var inputSheet = SpreadsheetApp.getActive().getSheetByName("Input");
  var processedStyle = [];
  var index = 2;
  var parentRow = 2;
  var processedParentCount = 0;
  var currentParentIndex = 2;
  var childIndex = 0;
  var childUpdateIndexMap = {};
  for (var i = 2; i <= inputSheet.getLastRow(); i++) {
    if (i == 2) {
      createHeadingForTargetSheet(main);
    }
    var style;
    var style_next_row;
    var products = inputSheet.getRange(i, 14).getValue();
    if (products == "Footwear") {
       style = inputSheet.getRange(i, 9).getValue();
       style_next_row = inputSheet.getRange(i + 1, 9).getValue();
    } else {
      style = inputSheet.getRange(i, 1).getValue();
      style_next_row = inputSheet.getRange(i + 1, 1).getValue();
    }
    
    if ((styleCountMap[style] == 1) || ((style == style_next_row) && processedStyle.indexOf(style) == -1)) {
      fillParentRow(main, inputSheet, index, i, categoryMap, amountMap, styleCountMap, childUpdateIndexMap);
      currentParentIndex = index;
      if (styleCountMap[style] > 1) {
        //Avoid increasing parent count for NV case
        parentRow = i + processedParentCount;
        processedParentCount++;
      }
      index++;
    }
    if (styleCountMap[style] == 1) {
      //Non variant, so need to avoid creating child rows.
      //Logger.log("NV index : ", index);
      continue;
    }
    //Logger.log("child index : ", index);
    var customSku = inputSheet.getRange(i, 16).getValue();
    var variation1 = inputSheet.getRange(i, 12).getValue();
    var newVariation1;
    if (variation1.includes("Puma")) {
      newVariation1 = variation1.replace("Puma", "PUMA");
    } else {
      newVariation1 = variation1;
    }
    var variationTwo = variation2(i);
    var temp_var_2 = variationTwo;
    if (temp_var_2.indexOf(" L") != -1) {
      temp_var_2 = temp_var_2.replace("Int:W", "").replace("Int:", "").replace("W", "").replace(" L", "/");
    }
    var mappingKey = variation1 + "_" + temp_var_2.replace("UK:", "").replace("FR:", "").replace("US:", "").replace("ASIA:", "").replace("Int:", "").replace(" yrs", "Y").replace("W", "").replace(" L", "/");
    main.getRange(i, 2).setValue("mappingKey : " + mappingKey);
    childIndex = childUpdateIndexMap[mappingKey];

    main.getRange(i, 3).setValue("childIndex : " + childIndex);
    childIndex = childIndex + parentRow + 1;
    main.getRange(i, 1).setValue(childUpdateIndexMap);
    main.getRange(childIndex, 11).setValue(variationTwo);
    processedStyle.push(style);
    //debugger;
    var amountMapValue = amountMap[customSku];
    if (amountMapValue != "" && amountMapValue != undefined) {
      var itemAmount = amountMapValue[3];
      var salePrice = amountMapValue[4];
    } else {
      main.getRange(childIndex, 17).setValue("error");
      main.getRange(childIndex, 14).setValue("error");
    }
    //will un-comment - if need to fill qty
    //    if(quantityMap !="" && quantityMap!= undefined){
    //      var quantityMapValue = quantityMap[customSku];
    //    } else {
    //      main.getRange(childIndex, 19).setValue("error");
    //    }
    //    if(quantityMapValue !="" && quantityMapValue!= undefined) {
    //      var noOfItem = quantityMapValue[1];
    //    } else {
    //      main.getRange(childIndex, 19).setValue("error");
    //    }

    var ageGroup = inputSheet.getRange(i, 4).getValue();
    var articleGroup = inputSheet.getRange(i, 6).getValue();


    var brand = inputSheet.getRange(i, 3).getValue();
    var regionalDispalyName = inputSheet.getRange(i, 2).getValue();
    var gender = inputSheet.getRange(i, 5).getValue();
    var activityGroup = inputSheet.getRange(i, 8).getValue();
    var articleType = inputSheet.getRange(i, 7).getValue();
    var searchColorName = inputSheet.getRange(i, 13).getValue();
    var images = inputSheet.getRange(i, 15).getValue();


    var longDescription = inputSheet.getRange(i, 25).getValue();
    var collection = inputSheet.getRange(i, 26).getValue();
    var material = inputSheet.getRange(i, 27).getValue();
    var materialLocal = inputSheet.getRange(i, 28).getValue();
    var upperMaterial = inputSheet.getRange(i, 29).getValue();
    var midSoleMaterial = inputSheet.getRange(i, 30).getValue();
    var outerSoleMaterial = inputSheet.getRange(i, 31).getValue();
    var shellMaterial = inputSheet.getRange(i, 32).getValue();

    var neck = inputSheet.getRange(i, 12).getValue();
    var sleeves = inputSheet.getRange(i, 12).getValue();
    var supportlevel = inputSheet.getRange(i, 12).getValue();
    var toeType = inputSheet.getRange(i, 33).getValue();
    var heelType = inputSheet.getRange(i, 34).getValue();
    var fastener = inputSheet.getRange(i, 66).getValue();
    var fit = inputSheet.getRange(i, 67).getValue();
    var pumaTechnology = inputSheet.getRange(i, 35).getValue();
    var technologyPurpose = inputSheet.getRange(i, 36).getValue();
    var colorName = inputSheet.getRange(i, 9).getValue();
    var title;
    var itemTitle;
    var newRegionalDisplayName;
    var getSearchColorName;
    if (regionalDispalyName.includes("’s")) {
      newRegionalDisplayName = regionalDispalyName.replace("’s", "'s™");
    } else {
      newRegionalDisplayName = regionalDispalyName;
    }
    if (searchColorName.includes(' - ')) {
      getSearchColorName = searchColorName.split(' - ')[1];
    }
    if (regionalDispalyName.includes("Men") || regionalDispalyName.includes("Women")) {
      title = formTitle(brand, newRegionalDisplayName, activityGroup, articleType,"",getSearchColorName,products);
      itemTitle = removeDuplicates(title);
    } else {
      title = formTitle(brand, newRegionalDisplayName, activityGroup, articleType, gender,getSearchColorName,products);
      itemTitle = removeDuplicates(title);
    }
    var mappedKey = ageGroup + '-' + gender + '-' + articleGroup + '-' + articleType + '-' + activityGroup;
    var categoryMapValue = categoryMap[mappedKey];

    if (categoryMapValue != undefined && categoryMapValue.length > 0) {
      main.getRange(childIndex, 21).setValue(categoryMapValue[1]);
    } else {
      main.getRange(index, 21).setValue("error");
    }
    debugger;
    main.getRange(childIndex, 4).setValue(customSku);
    main.getRange(childIndex, 5).setValue(replaceSplCharacter(itemTitle));
    if (salePrice != undefined && salePrice != "") {
      main.getRange(childIndex, 14).setValue(salePrice);
    }

    main.getRange(childIndex, 10).setValue(newVariation1);
    fillDefaultValues(main, childIndex, amountMapValue);

    main.getRange(childIndex, 17).setValue(itemAmount);
    //main.getRange(childIndex, 19).setValue(noOfItem);
    main.getRange(childIndex, 19).setValue(0);

    main.getRange(childIndex, 23).setValue(brand);
    main.getRange(childIndex, 24).setValue(colorName);
    main.getRange(childIndex, 30).setValue("1" + " X " + replaceSplCharacter(itemTitle));//package content
    main.getRange(childIndex, 31).setValue("sku.color_family=[\"" + newVariation1 + "\",]");
    main.getRange(childIndex, 32).setValue("sku.size=[\"" + variationTwo + "\",]");
    main.getRange(currentParentIndex, 31).setValue(main.getRange(currentParentIndex + 1, 31).getValue());
    main.getRange(currentParentIndex, 32).setValue(main.getRange(currentParentIndex + 1, 32).getValue());
    index++;
  }
}

function replaceSplCharacter(value) {
  return value.replace("â€œ", "“").replace("â€", "”").replace("â€˜", "‘").replace("â€™", "’").replace("â€”", "–").replace("â€“", "—").replace("â€¢", "-").replace("â€¦", "…").replace("Ã˜", "Ø").replace("Ã‚Â®", "®").replace("Â³", "³").replace("Â®", "®").replace("Ã¸", "Ÿ").replace("Ã‚", "Ÿ");
}

function fillDefaultValues(main, index, amountMapValue) {
  if (amountMapValue != "" && amountMapValue != undefined) {
    var salePrice = amountMapValue[4];
    if (salePrice != "") {
      main.getRange(index, 15).setValue("2024-05-10 00:00:00");
      main.getRange(index, 16).setValue("2024-06-10 23:59:00");
    }
  }
  main.getRange(index, 6).setValue("userTemplate-PH_PumaAccessories");
  main.getRange(index, 18).setValue("PHP"); //Currency
  main.getRange(index, 22).setValue("default");
  main.getRange(index, 25).setValue("No Warranty");
  main.getRange(index, 26).setValue("0.5");//package weight
  main.getRange(index, 27).setValue("15");//package height
  main.getRange(index, 28).setValue("12");//package length
  main.getRange(index, 29).setValue("12");//package width
}

function getItemTitle(regionalDispalyName, brand, gender, activityGroup, articleType,searchColorName,productsDivision) {
  var itemtitle;
  var title;
  var newRegionalDisplayName;
  var itemTitle;
  var getSearchColorName;
  if (regionalDispalyName.includes("’s")) {
    newRegionalDisplayName = regionalDispalyName.replace("’s", "'s™");
  } else {
    newRegionalDisplayName = regionalDispalyName;
  }
  if (searchColorName.includes(' - ')) {
    getSearchColorName = searchColorName.split(' - ')[1];
  }
  if (regionalDispalyName.includes("Men") || regionalDispalyName.includes("Women")) {
    title = formTitle(brand, newRegionalDisplayName, activityGroup, articleType,"",getSearchColorName,productsDivision);
    itemTitle = removeDuplicates(title);
  } else {
    title = formTitle(brand, newRegionalDisplayName, activityGroup, articleType, gender,getSearchColorName,productsDivision);
    itemTitle = removeDuplicates(title);
  }
  return itemTitle;
}

function formTitle(brand, newRegionalDisplayName, activityGroup, articleType, gender,searchColorName,productsDivision) {
  var title = "[NEW] ";
  if (brand.includes("Licence")) {
    var brandNameChanges= brand.replace("Licence", "PUMA")
    title += brandNameChanges;
  } else {
  title += brand;
  }
  if (gender != undefined && title.indexOf(gender) == -1) {
    // if (gender == "Male") {
    //   gender = "Men's"
    // } else if (gender == "Female") {
    //   gender = "Women's"
    // }
    if (gender == "Unisex") {
      title += " " + gender;
    }
  }
  if (title.indexOf(newRegionalDisplayName) == -1) {
    var checkRegionalDisplayName = "";
    if (newRegionalDisplayName.includes("Trainers")) {
      checkRegionalDisplayName = newRegionalDisplayName.replace("Trainers", "Shoes");
      title += " " + checkRegionalDisplayName;
    } else if (newRegionalDisplayName.includes("Sandals")) {
      checkRegionalDisplayName = newRegionalDisplayName.replace("Sandals", "Sports Sandals");
      title += " " + checkRegionalDisplayName;
    } else if (newRegionalDisplayName.includes("Slides")) {
      checkRegionalDisplayName = newRegionalDisplayName.replace("Slides", "Slides Slippers");
      title += " " + checkRegionalDisplayName;
    } else if (newRegionalDisplayName.includes("Trainer")) {
      checkRegionalDisplayName = newRegionalDisplayName.replace("Trainer", "Shoes");
      title += " " + checkRegionalDisplayName;
    } else {
      title += " " + newRegionalDisplayName;
    }
    
  }

  // if (title.indexOf(activityGroup) == -1) {
  //   title += " " + activityGroup;
  // }
  // if (title.indexOf(articleType) == -1) {
  //   title += " " + articleType;
  // }
  if (productsDivision == "Footwear") {
    if (title.indexOf(searchColorName) == -1) {
      title += " (" + searchColorName + ") ";
    }
   }
 
  return title;
}

function countNoOfItems() {
  //debugger;
  var inputSheet = SpreadsheetApp.getActive().getSheetByName("Input"); 
  var colorNumberValues =[];
  var styleValues=[];
  for (var i=2;i<=inputSheet.getLastRow();i++) {
    var products = inputSheet.getRange(i, 14).getValue();
    if (products == "Footwear") {
    colorNumberValues.push(inputSheet.getRange(i ,9).getValue());
  }
   else {
    styleValues.push (inputSheet.getRange(i,1).getValue()); 
  } 
  } 
   var result = {};
  colorNumberValues.forEach(function (x) {
    result[x] = (result[x] || 0) + 1;
  });

  styleValues.forEach(function (x) {
    result[x] = (result[x] || 0) + 1;
  });

   return result; 
}

function fillParentRow(main, inputSheet, index, i, categoryMap, amountMap, styleCountMap, childUpdateIndexMap) {
  var customSku = inputSheet.getRange(i, 16).getValue();
  var ageGroup = inputSheet.getRange(i, 4).getValue();
  var articleGroup = inputSheet.getRange(i, 6).getValue();
  var brand = inputSheet.getRange(i, 3).getValue();
  var regionalDispalyName = inputSheet.getRange(i, 2).getValue();
  var gender = inputSheet.getRange(i, 5).getValue();
  var activityGroup = inputSheet.getRange(i, 8).getValue();
  var articleType = inputSheet.getRange(i, 7).getValue();
  var variation1 = inputSheet.getRange(i, 12).getValue();
  var searchColorName = inputSheet.getRange(i, 13).getValue();
  var longDescription = inputSheet.getRange(i, 25).getValue();
  var collection = inputSheet.getRange(i, 26).getValue();
  var material = inputSheet.getRange(i, 27).getValue();
  var materialLocal = inputSheet.getRange(i, 28).getValue();
  var upperMaterial = inputSheet.getRange(i, 29).getValue();
  var midSoleMaterial = inputSheet.getRange(i, 30).getValue();
  var outerSoleMaterial = inputSheet.getRange(i, 31).getValue();
  var shellMaterial = inputSheet.getRange(i, 32).getValue();

  var neck = inputSheet.getRange(i, 12).getValue();
  var sleeves = inputSheet.getRange(i, 12).getValue();
  var supportlevel = inputSheet.getRange(i, 12).getValue();
  var toeType = inputSheet.getRange(i, 33).getValue();
  var heelType = inputSheet.getRange(i, 34).getValue();
  var fastener = inputSheet.getRange(i, 66).getValue();
  var fit = inputSheet.getRange(i, 67).getValue();
  var pumaTechnology = inputSheet.getRange(i, 35).getValue();
  var technologyPurpose = inputSheet.getRange(i, 36).getValue();
  var shortDescription = inputSheet.getRange(i, 24).getValue();
  var care = inputSheet.getRange(i, 43).getValue();
  var careLabel = inputSheet.getRange(i, 44).getValue();
  var productsDivision = inputSheet.getRange(i, 14).getValue();

  var itemTitle = getItemTitle(regionalDispalyName, brand, gender, activityGroup, articleType,searchColorName,productsDivision);
  main.getRange(index, 5).setValue(replaceSplCharacter(itemTitle));
  main.getRange(index, 30).setValue("1" + " X " + replaceSplCharacter(itemTitle));//package content

  var mappedKey = ageGroup + '-' + gender + '-' + articleGroup + '-' + articleType + '-' + activityGroup;
  var categoryMapValue = categoryMap[mappedKey];
  var amountMapValue = amountMap[customSku];

  if (amountMapValue != "" && amountMapValue != undefined) {
    var itemAmount = amountMapValue[3];
    main.getRange(index, 17).setValue(itemAmount);
  }

  //Recently added script upto line 90
  var ean = inputSheet.getRange(i, 16).getValue();
  var act_group = inputSheet.getRange(i, 8).getValue();
  if (act_group == "Prime/Select") {
    act_group = "Others";
  } else if (act_group == "Sport Classics" || act_group == "Evolution" || act_group == "Basics" || act_group == "Kids" || act_group == "Auto") {
    act_group = "Lifestyle";
  }
  var material = inputSheet.getRange(i, 27).getValue();
  var val1 = "";
  if (material.indexOf("100% polyester") != -1) {
    val1 = 'normal.clothing_material=["Polyester",]';
  } else if (material.indexOf("100% nylon") != -1) {
    val1 = 'normal.clothing_material=["Nylon",]';
  } else if (material.indexOf("100% cotton") != -1) {
    val1 = 'normal.clothing_material=["Cotton",]';
  } else if (material.indexOf("polyester") != -1 && material.indexOf("nylon") != -1) {
    val1 = 'normal.clothing_material=["Polyester+Nylon",]';
  } else if (material.indexOf("polyester") != -1 && material.indexOf("cotton") != -1) {
    val1 = 'normal.clothing_material=["Polyester+Cotton",]';
  } else if (material.indexOf("polyester") != -1 && material.indexOf("elastane") != -1) {
    val1 = 'normal.clothing_material=["Polyester+Elasteane",]';
  } else if (material.indexOf("polyester") != -1 && material.indexOf("spandex") != -1) {
    val1 = 'normal.clothing_material=["Polyester+Spandex",]';
  }
  var itemSpecIndex = 33;
  main.getRange(index, itemSpecIndex).setValue('normal.activity_type=["' + act_group + '",]');
  if (val1 != "") {
    itemSpecIndex++;
    main.getRange(index, itemSpecIndex).setValue(val1);
  }
  itemSpecIndex++;
  main.getRange(index, itemSpecIndex).setValue('normal.delivery_option_economy=["No",]');
  if (articleGroup != undefined && articleGroup != "") {
    if (articleGroup.toLowerCase() == "tops") {
      var tops_type = "";
      if (articleType == "Tee") {
        tops_type = "T-Shirts";
      } else if (articleType == "Polo") {
        tops_type = "Polo";
      }
      if (tops_type != "") {
        itemSpecIndex++;
        main.getRange(index, itemSpecIndex).setValue('normal.tops_type=["' + tops_type + '",]');
      }
    }
  }

  if (categoryMapValue != undefined && categoryMapValue.length > 0) {
    main.getRange(index, 21).setValue(categoryMapValue[1]);
  } else {
    main.getRange(index, 21).setValue("error");
  }
  var style = "";
   if (productsDivision == "Footwear") {
      style = inputSheet.getRange(i, 9).getValue();
   } else {
      style = inputSheet.getRange(i, 1).getValue();
   }
 
  var shortDescrition = getShortDescription(shortDescription, brand, searchColorName, gender, activityGroup, collection, material, materialLocal, upperMaterial,
    midSoleMaterial, outerSoleMaterial, shellMaterial, toeType,
    heelType, fastener, fit, pumaTechnology, technologyPurpose, inputSheet, index, style);

  var styleCount = styleCountMap[style];
  var parentQuantity = sortChildIndexBasedOnSize(childUpdateIndexMap, styleCount, i, index);

  fillDefaultValues(main, index, amountMapValue);
  var templateAttributeValueList = getTemplateAttribute1();
  var sizeChartKey = ageGroup + "-" + gender + "-" + articleGroup + "-" + articleType;
  var templateAttributeValue = templateAttributeValueList[sizeChartKey];
  var templateAttribute1 = "";
  var templateAttribute4 = "";
  var templateAttribute5 = "";
  if (templateAttributeValue != "" && templateAttributeValue != undefined) {
    templateAttribute1 = templateAttributeValue[1];
  }
  if (care != "" && care != undefined) {
    templateAttribute4 += "<p><strong>Care:</strong>" + care + "<p>";
  }
  if (careLabel != "" && careLabel != undefined) {
    templateAttribute4 += "<p><strong>Care Label:</strong>" + careLabel + "<p>";
  }

  fillTempateAttributes(main, templateAttribute1, templateAttribute4, templateAttribute5, index, longDescription);
  //main.getRange(index, 19).setValue(parentQuantity);
  main.getRange(index, 19).setValue(0);
  if (styleCountMap[style] > 1) {
    //fill only for parent
    main.getRange(index, 4).setValue(style);
    main.getRange(index, 9).setValue(styleCount);
    main.getRange(index, 10).setValue("color_family");
    main.getRange(index, 11).setValue("size");
  } else {
    main.getRange(index, 4).setValue(customSku);
  }
  main.getRange(index, 13).setValue("<ul>" + replaceSplCharacter(shortDescrition) + "</ul>");
  main.getRange(index, 23).setValue(brand);
  main.getRange(index, 24).setValue(style);
  //getNumberOfItem(style,inputSheet);
}

function sortChildIndexBasedOnSize(childUpdateIndexMap, styleCount, j, index) {
  var inputSheet = SpreadsheetApp.getActive().getSheetByName("Input");
  var childEndIndex = j + styleCount - 1;
  var sizeValues = inputSheet.getRange("L" + j + ":V" + childEndIndex).getValues();
  var tempArray = [];
  var childArray = [];
  var colourArray = [];
  var colourValueCountMap = {};
  var availableSizeValues = {};
  var customSKUArray = [];
  var parentQuantity = 0;
  for (var i = 0; i < sizeValues.length; i++) {
    var value1 = sizeValues[i];
    var sizeValue = variation2(i + j).replace("UK:", "").replace("FR:", "").replace("US:", "").replace("ASIA:", "").replace("Int:", "").replace(" yrs", "Y");
    //baskar - changing
    //Logger.log("checking sizeValue 1 : " + sizeValue);
    if (sizeValue.indexOf(" L") != -1) {
      sizeValue = sizeValue.replace("Int:W", "").replace("Int:", "").replace("W", "").replace(" L", "/");
    }
    //Logger.log("checking sizeValue 2 : " + sizeValue);
    var customSKU = value1[4];
    var colour = value1[0];
    parentQuantity += value1[5];
    customSKUArray.push(customSKU);
    if (tempArray.indexOf(sizeValue) == -1) {
      tempArray.push(sizeValue);
    }
    childArray.push(sizeValue);
    //    Logger.log("variant", variation2(i+j).replace("UK:", "").replace("FR:", "").replace("US:", "").replace("ASIA:", "").replace("Int:","").replace(" yrs", "Y"));
    var count = 1;
    if (colourValueCountMap[colour] != undefined) {
      count = colourValueCountMap[colour] + 1;
    }
    availableSizeValues[sizeValue] = "1";
    colourArray.push(colour);
    colourValueCountMap[colour] = count;
  }
  var sortByStringValue = false;
  if (childArray.indexOf("3XS") != -1 || childArray.indexOf("XXXS") != -1 || childArray.indexOf("XXS") != -1 || childArray.indexOf("XS") != -1
    || childArray.indexOf("S") != -1 || childArray.indexOf("S/M") != -1 || childArray.indexOf("M") != -1 || childArray.indexOf("M/L") != -1
    || childArray.indexOf("L") != -1 || childArray.indexOf("L/XL") != -1 || childArray.indexOf("XL") != -1 || childArray.indexOf("XXL") != -1
    || childArray.indexOf("XXXL") != -1 || childArray.indexOf("3XL") != -1 || childArray.indexOf("4XL") != -1 || childArray.indexOf("5XL") != -1
    || childArray.indexOf("6XL") != -1 || childArray.indexOf("1-2Y") != -1 || childArray.indexOf("2-3Y") != -1 || childArray.indexOf("3-4Y") != -1
    || childArray.indexOf("4-5Y") != -1 || childArray.indexOf("5-6Y") != -1 || childArray.indexOf("6-7Y") != -1
    || childArray.indexOf("7-8Y") != -1 || childArray.indexOf("8-9Y") != -1 || childArray.indexOf("9-10Y") != -1
    || childArray.indexOf("10-11Y") != -1 || childArray.indexOf("11-12Y") != -1 || childArray.indexOf("12-13Y") != -1
    || childArray.indexOf("13-14Y") != -1 || childArray.indexOf("14-15Y") != -1 || childArray.indexOf("15-16Y") != -1
    || childArray.indexOf("6Y") != -1 || childArray.indexOf("8Y") != -1 || childArray.indexOf("10Y") != -1
    || childArray.indexOf("12Y") != -1 || childArray.indexOf("14Y") != -1 || childArray.indexOf("16Y") != -1
    || childArray.indexOf("18Y") != -1 || childArray.indexOf("20Y") != -1 || childArray.indexOf("OSFA") != -1 || childArray.indexOf("One size") != -1
    || childArray.indexOf("UA") != -1 || childArray.indexOf("Mini") != -1
    || childArray.indexOf("Kids") != -1 || childArray.indexOf("Adult") != -1 || childArray.indexOf("Youth") != -1) {
    sortByStringValue = true;
  }
  if (sortByStringValue) {
    sortByStringValues(childArray, tempArray, customSKUArray, childUpdateIndexMap, colourArray, colourValueCountMap, availableSizeValues);
  } else {
    tempArray.sort(function (a, b) {
      if (isNaN(a) && isNaN(b)) {
        return a.localeCompare(b)
      } else {
        return a - b
      }
    });
    sortByIntValues(childArray, tempArray, customSKUArray, childUpdateIndexMap, colourArray, colourValueCountMap);
  }
  return parentQuantity;
}

function sortByIntValues(childArray, tempArray, customSKUArray, childUpdateIndexMap, colourArray, colourValueCountMap) {
  var colourSizeMap = [];
  var availableColour = [];
  for (var i = 0; i < childArray.length; i++) {
    var size = childArray[i];
    var colour = colourArray[i];
    if (availableColour.indexOf(colour) == -1) {
      availableColour.push(colour);
    }
    colourSizeMap.push(colour + "_" + size);
  }
  var loopSize = tempArray;
  var colourCount = 0;
  for (var i = 0; i < availableColour.length; i++) {
    var colour = availableColour[i];
    for (var j = 0; j < loopSize.length; j++) {
      var size = loopSize[j];
      var key = colour + "_" + size;
      if (colourSizeMap.indexOf(key) != -1) {
        childUpdateIndexMap[key] = colourCount;
        colourCount++;
      }
    }
  }
}

function sortByStringValues(childArray, tempArray, customSKUArray, childUpdateIndexMap, colourArray, colourValueCountMap, availableSizeValues) {
  var colourSizeMap = [];
  var availableColour = [];
  for (var i = 0; i < childArray.length; i++) {
    var size = childArray[i];
    var colour = colourArray[i];
    if (availableColour.indexOf(colour) == -1) {
      availableColour.push(colour);
    }
    colourSizeMap.push(colour + "_" + size);
  }
  var loopSize = ["3XS", "XXXS", "XXS", "XS", "S", "S/M", "M", "M/L", "L", "L/XL", "XL", "XXL", "XXXL", "3XL", "4XL", "5XL", "6XL", "1-2Y", "2-3Y", "3-4Y", "4-5Y", "5-6Y", "6-7Y", "7-8Y", "8-9Y", "9-10Y", "10-11Y", "11-12Y", "12-13Y", "13-14Y", "14-15Y", "15-16Y", "16-17Y", "17-18Y", "18-19Y", "19-20Y", "6Y", "8Y", "10Y", "12Y", "14Y", "16Y", "18Y", "20Y", "OSFA", "One size", "UA", "Mini", "Kids", "Adult", "Youth"];
  var colourCount = 0;
  for (var i = 0; i < availableColour.length; i++) {
    var colour = availableColour[i];
    for (var j = 0; j < loopSize.length; j++) {
      var size = loopSize[j];
      var key = colour + "_" + size;
      if (colourSizeMap.indexOf(key) != -1) {
        childUpdateIndexMap[key] = colourCount;
        colourCount++;
      }
    }
  }
}

function getTemplateAttribute1() {
  var sizeChartMap = new Object();
  var sizeChartSheet = SpreadsheetApp.getActive().getSheetByName("Size chart");
  var values = sizeChartSheet.getRange("A2:B" + sizeChartSheet.getLastRow()).getValues();
  //var mappedKey = ageGroup+ "-"+gender+"-"+articleGroup+ "-"+articleType+ "-"+activityGroup;
  //var mappedKey = "Adults - Unisex - Undefined - Low Boot - Indoor"
  for (var i = 0; i < values.length; i++) {
    var sizeChartObj = values[i];
    var mappedKey = sizeChartObj[0];
    sizeChartMap[mappedKey] = sizeChartObj;
  }
  return sizeChartMap;
}

function removeDuplicates(title) {
  var str = title.split(" ");
  var result = [];
  for (var i = 0; i < str.length; i++) {
    if (result.indexOf(str[i]) === -1) {
      result.push(str[i]);
    }
  }
  return result.join(" ");
}

function getShortDescription(shortDescription, brand, searchColorName, gender, activityGroup, collection, material, materialLocal, upperMaterial,
  midSoleMaterial, outerSoleMaterial, shellMaterial, toeType,
  heelType, fastener, fit, pumaTechnology, technologyPurpose, inputSheet, index, style) {
  var shortDesc = shortDescription;
  if (brand != "" && brand != undefined) {
    shortDesc += "<li>Brand : " + brand + "</li>";
  }
  if (searchColorName != "" && searchColorName != undefined) {
    shortDesc += "<li>Color Name : " + searchColorName + "</li>";
  }
  if (gender != "" && gender != undefined) {
    shortDesc += "<li>Gender : " + gender + "</li>";
  }
  if (activityGroup != "" && activityGroup != undefined) {
    shortDesc += "<li>Activity Group : " + activityGroup + "</li>";
  }
  if (collection != "" && collection != undefined) {
    shortDesc += "<li>Collection : " + collection + "</li>";
  }
  if (material != "" && material != undefined && material != "Other") {
    var newMaterial = "<li>Material : " + material + "</li>";
    var main_material_2_present = false;
    if (newMaterial.indexOf("Main Material 1") != -1) {
      newMaterial = newMaterial.replace("<li>Material : ", "<li>");
    }
    if (newMaterial.indexOf("Main Material 2") != -1) {
      main_material_2_present = true;
      newMaterial = newMaterial.replace("<li>Material : ", "<li>");
      newMaterial = newMaterial.replace("Main Material 2", "</li><li>Main Material 2");
    }
    if (newMaterial.indexOf("Main Material 3") != -1) {
      newMaterial = newMaterial.replace("<li>Material : ", "<li>");
      if (!main_material_2_present) {
        newMaterial = newMaterial.replace("Main Material 3", "</li><li>Main Material 2");
      } else {
        newMaterial = newMaterial.replace("Main Material 3", "</li><li>Main Material 3");
      }
    }
    shortDesc += newMaterial;
  }
  if (materialLocal != "" && materialLocal != undefined && materialLocal != "Other") {
    shortDesc += "<li>Material Local : " + materialLocal + "</li>";
  }
  if (upperMaterial != "" && upperMaterial != undefined && upperMaterial != "Other") {
    shortDesc += "<li>Upper Material : " + upperMaterial + "</li>";
  }
  if (midSoleMaterial != "" && midSoleMaterial != undefined && midSoleMaterial != "Other") {
    shortDesc += "<li>Mid Sole Material : " + midSoleMaterial + "</li>";
  }
  if (outerSoleMaterial != "" && outerSoleMaterial != undefined && outerSoleMaterial != "Other") {
    shortDesc += "<li>Outer Sole Material : " + outerSoleMaterial + "</li>";
  }
  if (shellMaterial != "" && shellMaterial != undefined && shellMaterial != "Other") {
    shortDesc += "<li>Shell Material : " + shellMaterial + "</li>";
  }
  if (toeType != "" && toeType != undefined) {
    shortDesc += "<li>Toe Type : " + toeType + "</li>";
  }
  if (heelType != "" && heelType != undefined) {
    shortDesc += "<li>Heel Type : " + heelType + "</li>";
  }
  if (fastener != "" && fastener != undefined) {
    shortDesc += "<li>Fastener : " + fastener + "</li>";
  }
  if (fit != "" && fit != undefined) {
    shortDesc += "<li>Fit : " + fit + "</li>";
  }
  if (pumaTechnology != "" && pumaTechnology != undefined) {
    shortDesc += "<li>PUMA Technology : " + pumaTechnology + "</li>";
  }
  if (technologyPurpose != "" && technologyPurpose != undefined) {
    shortDesc += "<li>Technology Purpose : " + technologyPurpose + "</li>";
  }
  if (style != undefined && style != "") {
    shortDesc += "<li>Style Number : " + style + "</li>";
  }
  return shortDesc;
}

function capitalizeFirstLetters(str) {
  var strVal = '';
  str = str.split(' ');
  for (var chr = 0; chr < str.length; chr++) {
    strVal += str[chr].substring(0, 1).toUpperCase() + str[chr].substring(1, str[chr].length) + ' '
  }
  return strVal;
}

function fillTempateAttributes(main, templateAttribute1, templateAttribute4, templateAttribute5, index, longDescription) {
  var templateAttribute2 = "";
  var templateAttribute3 = "";
  if (longDescription.includes("FEATURES")) {
    templateAttribute2 = longDescription.substring(longDescription.indexOf("<p>"), longDescription.indexOf("FEATURES"));
    templateAttribute3 = longDescription.substring(longDescription.indexOf("FEATURES"));
  } else {
    if (longDescription.includes("DETAILS")) {
      templateAttribute2 = longDescription.substring(longDescription.indexOf("<p>"), longDescription.indexOf("DETAILS"));
      templateAttribute3 = longDescription.substring(longDescription.indexOf("DETAILS"));
    } else {
      templateAttribute2 = longDescription.substring(longDescription.indexOf("<p>"));
    }
  }
  //templateAttribute1 = capitalizeFirstLetters(templateAttribute1);
  main.getRange(index, 56).setValue("sizechart=" + templateAttribute1);
  if (templateAttribute2 != "") {
    main.getRange(index, 57).setValue("description=" + replaceSplCharacter(templateAttribute2).replace("<h3>", ""));
  }
  if (templateAttribute3 != "") {
    main.getRange(index, 58).setValue("productstory=<h3>" + replaceSplCharacter(templateAttribute3));
  }
  if (templateAttribute4 != "") {
    main.getRange(index, 59).setValue("care=" + replaceSplCharacter(templateAttribute4));
  }
  //   if(templateAttribute5!=""){
  //    main.getRange(index, 60).setValue("care label="+ templateAttribute5);
  //  }

}

function variation2(i) {
  var main = SpreadsheetApp.getActive().getSheetByName("main");
  var inputSheet = SpreadsheetApp.getActive().getSheetByName("Input");
  var productDivision = inputSheet.getRange(i, 14).getValue();
  var sizeUK = inputSheet.getRange(i, 22).getValue();
  var sizeFR = inputSheet.getRange(i, 21).getValue();
  var sizeAsia = inputSheet.getRange(i, 23).getValue();
  var sizeUS = inputSheet.getRange(i, 20).getValue();
  var variation2;

  if (productDivision == "Footwear") {
    if (sizeUK != "") {
      if (isNaN(sizeUK)) {
        variation2 = "Int:" + sizeUK;
      } else {
        variation2 = "UK:" + sizeUK;
      }
    } else {
      if (isNaN(sizeFR)) {
        variation2 = "Int:" + sizeFR;
      } else {
        variation2 = "US:" + sizeFR;
      }
    }
  }
  if (productDivision == "Apparel") {
    if (sizeUK != "") {
      if (isNaN(sizeUK)) {
        variation2 = "Int:" + sizeUK;
      } else {
        variation2 = "UK:" + sizeUK;
      }
    } else if (sizeUK == "" && sizeUS != "") {
      if (isNaN(sizeUS)) {
        variation2 = "Int:" + sizeUS;
      } else {
        variation2 = "US:" + sizeUS;
      }
    } else {
      if (isNaN(sizeAsia)) {
        variation2 = "Int:" + sizeAsia;
      } else {
        variation2 = "ASIA:" + sizeAsia;
      }
    }
  }
  if (productDivision == "Accessories") {
    if (sizeUK != "") {
      if (isNaN(sizeUK)) {
        variation2 = "Int:" + sizeUK;
      } else {
        variation2 = "UK:" + sizeUK;
      }
    } else {
      if (isNaN(sizeUS)) {
        variation2 = "Int:" + sizeUS;
      } else {
        variation2 = "US:" + sizeUS;
      }
    }

  }

  if (productDivision == "Socks") {
    if (sizeUK != "") {
      if (isNaN(sizeUK)) {
        variation2 = "Int:" + sizeUK;
      } else {
        variation2 = "UK:" + sizeUK;
      }
    } else {
      if (isNaN(sizeFR)) {
        variation2 = "Int:" + sizeFR;
      } else {
        variation2 = "US:" + sizeFR;
      }
    }

  }


  if (variation2.includes("/")) {
    if (variation2.includes("S/M") || variation2.includes("M/L") || variation2.includes("L/XL")) {
      return variation2;
    } else {
      return variation2.replace("Int:", "Int:W").replace("/", " L");
    }
  } else if (variation2.includes("OSFA") || variation2.includes("Mini") || variation2.includes("Kids") || variation2.includes("Youth") || variation2.includes("Adult") || variation2.includes("UA")) {
    if (variation2.includes("OSFA")) {
      return "Int:One size";
    }
    if (variation2.includes("Mini")) {
      return "Int:XS";
    }
    if (variation2.includes("Kids")) {
      return "Int:S";
    }
    if (variation2.includes("Youth")) {
      return "Int:M";
    }
    if (variation2.includes("Adult")) {
      return "Int:L";
    }
    if (variation2.includes("UA")) {
      return "Int:UA";
    }
  } else {
    if (variation2.includes("Youth")) {
      return variation2;
    } else {
      return variation2.replace("Y", " yrs");
    }
  }
}

function constructAmountMap() {
  //debugger;
  var amountMap = new Object();
  var priceSheet = SpreadsheetApp.getActive().getSheetByName("Price Sheet");
  var values = priceSheet.getRange("A2:E" + priceSheet.getLastRow()).getValues();
  for (var i = 0; i < values.length; i++) {
    var priceObj = values[i];
    var customSKU = priceObj[2];
    //    var colorName = priceObj[8];
    amountMap[customSKU] = priceObj;
  }
  return amountMap;
}

function constructQuantityMap() {
  var quantitytMap = new Object();
  var quantitySheet = SpreadsheetApp.getActive().getSheetByName("Stock sheet");
  var values = quantitySheet.getRange("A2:B" + quantitySheet.getLastRow()).getValues();
  for (var i = 0; i < values.length; i++) {
    var quantityObj = values[i];
    var customSKU = quantityObj[0];
    quantitytMap[customSKU] = quantityObj;
  }
  return quantitytMap;
}

function constructCategoryMap() {
  //debugger;
  var categoryMap = new Object();
  var inputSheet = SpreadsheetApp.getActive().getSheetByName("Input");
  var categorySheet = SpreadsheetApp.getActive().getSheetByName("Category sheet");
  var values = categorySheet.getRange("A2:C" + categorySheet.getLastRow()).getValues();
  for (var i = 0; i < values.length; i++) {
    var categoryObj = values[i];
    var categoryName = categoryObj[0];
    categoryMap[categoryName] = categoryObj;
  }
  return categoryMap
}

function createHeadingForTargetSheet(target) {
  var headings = ["SKU", "status", "errorDetails", "customSKU", "itemTitle", "itemDescription1", "itemDescription2", "itemDescription3", "noOfVariants", "variation1", "variation2", "variation3", "shortDescription", "salePrice", "saleStartDate", "saleEndDate", "itemAmount", "currencyCode", "noOfItem", "imageURI", "categoryID", "taxClass", "brand", "model", "warrantyType", "packageWeight(kg)", "packageHeight(cm)", "packageLength(cm)", "packageWidth(cm)", "packageContent", "itemSpecifics1", "itemSpecifics2", "itemSpecifics3", "itemSpecifics4", "itemSpecifics5", "itemSpecifics6", "itemSpecifics7", "itemSpecifics8", "itemSpecifics9", "itemSpecifics10", "itemSpecifics11", "itemSpecifics12", "itemSpecifics13", "itemSpecifics14", "itemSpecifics15", "itemSpecifics16", "itemSpecifics17", "itemSpecifics18", "itemSpecifics19", "itemSpecifics20", "itemSpecifics21", "itemSpecifics22", "itemSpecifics23", "itemSpecifics24", "itemSpecifics25", "templateAttribute1", "templateAttribute2", "templateAttribute3", "templateAttribute4", "templateAttribute5", "postAsNonVariant"];
  for (var i = 0; i < headings.length; i++) {
    target.getRange(1, i + 1).setValue(headings[i]);
  }
}
