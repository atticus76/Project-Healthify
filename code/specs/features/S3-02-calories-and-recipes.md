# Track calories and discover recipes that fit the remaining daily target

### User Story

**As a** signed-in Healthify user, **I need** to see my calorie target, track what I burn and eat, and find recipes that fit the rest of my day, **so that** I can decide what to eat next without calculating calories myself.

### Details and Assumptions

- The MyPlate.food plan supplies the daily target. USDA FoodData Central supplies food and portion data for logging dishes. MyPlate.food supplies recipes and nutrition per serving.
- Burned and consumed counters cover the period since the last manual reset. Recipe recommendations use the daily target minus intake logged since local midnight. Resetting the counters preserves meal history.
- Calorie limits in recipe search and suggestions apply to one serving.

### Acceptance Criteria

```gherkin
Feature: Track calories and discover recipes

  Background:
    Given I am signed in to Healthify

  Scenario: Complete a missing profile and see my target
    Given my health profile is missing height or activity level
    When I open the dashboard
    Then the Calories card asks me to complete my Health Profile
    When I save my age, supported gender, height, weight, and activity level
    And MyPlate returns a daily calorie target
    Then I see that target alongside my burned and consumed calories

  Scenario: Track burned calories without counting the same interval twice
    Given I have enabled the emulator or connected a Fitbit
    When Healthify receives calorie readings for overlapping intervals
    Then the Burned display counts the overlapping time only once

  Scenario: Log a dish by portion
    Given USDA lists a dish at 120 kcal per serving
    When I select "Add Calories by Dish", find the dish, and choose 1.5 servings
    Then I see a preview of 180 kcal
    When I confirm the entry
    Then my consumed calories increase by 180 kcal

  Scenario: Enter a known calorie amount and reset tracking
    When I enter 250 kcal and select "Add Calories"
    Then my consumed calories increase by 250 kcal
    When I select "Reset"
    Then burned and consumed start again at zero
    And my daily target and today's logged meals are preserved

  Scenario: Search recipes and open a result
    Given at least 16 recipes match my keyword and filters
    When I select "Search Recipe" and submit the search
    Then I see eight named recipe images in two columns and four rows
    When I scroll to the end of the results
    Then eight more matching recipes appear after the first batch
    When I select a recipe
    Then I see its ingredients, directions, serving information, and available nutrition

  Scenario: Rank suggestions against my remaining daily target
    Given my target is 2200 kcal and I have logged 1500 kcal today
    When Healthify selects suggested recipes
    Then every suggested serving is at most 700 kcal
    And servings from 300 to 700 kcal rank ahead of lighter servings
    And within each range my preferred food group ranks first
    And closeness to 500 kcal ranks next, with higher ratings breaking ties
    And I see up to ten suggestions

  Scenario Outline: Explain how recipes are selected
    When I <action> the information icon beside "Suggested Recipes"
    Then I see an explanation beginning "Personalized Suggested Recipes are selected based on"
    And it explains the calorie range, food-group preference, and ranking

    Examples:
      | action     |
      | hover over |
      | click      |
      | focus on   |

  Scenario: Browse a stable set of suggestions
    Given ten recipes are available and the dashboard is open
    When ten seconds pass with no dialog open
    Then the carousel advances one recipe and wraps from the tenth to the first
    And the arrows let me move through the same set manually
    And selecting the recipe image opens its details

  Scenario Outline: Refresh personalized suggestions
    Given suggestions have already been selected for today
    When <trigger>
    Then Healthify requests suggestions using my current remaining calories and preference

    Examples:
      | trigger                                                       |
      | I log a meal and still have calories remaining                |
      | my remaining budget changes by at least 200 kcal and is positive |
      | a new local day begins and I have a daily target              |
      | I change my preferred food group with calories remaining      |
      | I click the refresh button with calories remaining            |

  Scenario: No calorie budget remains
    Given I have reached my daily calorie target
    When I view Suggested Recipes
    Then I see a message explaining why there are no personalized suggestions
    And I can still search the recipe catalog
```
