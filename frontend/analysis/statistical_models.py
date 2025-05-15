import numpy as np
import scipy.stats as stats
from typing import Dict, List, Any, Tuple, Optional

class SentimentDistribution:
    """Represents a statistical distribution of sentiment scores."""
    
    def __init__(self, 
                 power_scores: List[float] = None, 
                 moral_scores: List[float] = None):
        """
        Initialize with optional lists of observed scores.
        
        Args:
            power_scores: List of power dimension scores (-2 to +2)
            moral_scores: List of moral dimension scores (-2 to +2)
        """
        self.power_scores = power_scores or []
        self.moral_scores = moral_scores or []
        
        # Cached distribution parameters
        self._power_mean = None
        self._power_std = None
        self._moral_mean = None
        self._moral_std = None
        
        # Update distribution parameters if data is provided
        if power_scores:
            self._update_power_params()
        if moral_scores:
            self._update_moral_params()
    
    def add_scores(self, power_score: float, moral_score: float):
        """Add a new pair of sentiment scores to the distribution."""
        self.power_scores.append(power_score)
        self.moral_scores.append(moral_score)
        self._update_power_params()
        self._update_moral_params()
    
    def add_multiple_scores(self, power_scores: List[float], moral_scores: List[float]):
        """Add multiple pairs of sentiment scores to the distribution."""
        if len(power_scores) != len(moral_scores):
            raise ValueError("Power and moral score lists must be the same length")
        
        self.power_scores.extend(power_scores)
        self.moral_scores.extend(moral_scores)
        self._update_power_params()
        self._update_moral_params()
    
    def _update_power_params(self):
        """Update cached parameters for power score distribution."""
        if self.power_scores:
            self._power_mean = np.mean(self.power_scores)
            self._power_std = np.std(self.power_scores) if len(self.power_scores) > 1 else 1.0
        else:
            self._power_mean = 0
            self._power_std = 1.0
    
    def _update_moral_params(self):
        """Update cached parameters for moral score distribution."""
        if self.moral_scores:
            self._moral_mean = np.mean(self.moral_scores)
            self._moral_std = np.std(self.moral_scores) if len(self.moral_scores) > 1 else 1.0
        else:
            self._moral_mean = 0
            self._moral_std = 1.0
    
    @property
    def power_mean(self) -> float:
        """Get the mean of power scores."""
        return self._power_mean if self._power_mean is not None else 0
    
    @property
    def power_std(self) -> float:
        """Get the standard deviation of power scores."""
        return self._power_std if self._power_std is not None else 1.0
    
    @property
    def moral_mean(self) -> float:
        """Get the mean of moral scores."""
        return self._moral_mean if self._moral_mean is not None else 0
    
    @property
    def moral_std(self) -> float:
        """Get the standard deviation of moral scores."""
        return self._moral_std if self._moral_std is not None else 1.0
    
    @property
    def count(self) -> int:
        """Get the number of observations in the distribution."""
        return len(self.power_scores)
    
    def power_pdf(self, x: float) -> float:
        """Calculate the probability density for a given power score."""
        return stats.norm.pdf(x, loc=self.power_mean, scale=self.power_std)
    
    def moral_pdf(self, x: float) -> float:
        """Calculate the probability density for a given moral score."""
        return stats.norm.pdf(x, loc=self.moral_mean, scale=self.moral_std)
    
    def power_cdf(self, x: float) -> float:
        """Calculate the cumulative probability for a power score."""
        return stats.norm.cdf(x, loc=self.power_mean, scale=self.power_std)
    
    def moral_cdf(self, x: float) -> float:
        """Calculate the cumulative probability for a moral score."""
        return stats.norm.cdf(x, loc=self.moral_mean, scale=self.moral_std)
    
    def power_percentile(self, x: float) -> float:
        """Get the percentile (0-100) for a given power score."""
        return self.power_cdf(x) * 100
    
    def moral_percentile(self, x: float) -> float:
        """Get the percentile (0-100) for a given moral score."""
        return self.moral_cdf(x) * 100
    
    def get_power_interval(self, confidence: float = 0.95) -> Tuple[float, float]:
        """Get confidence interval for power scores."""
        if not self.power_scores:
            return (-2.0, 2.0)
        
        alpha = 1 - confidence
        interval = stats.t.interval(
            confidence=confidence,
            df=len(self.power_scores)-1,
            loc=self.power_mean,
            scale=self.power_std/np.sqrt(len(self.power_scores))
        )
        return (max(-2.0, interval[0]), min(2.0, interval[1]))
    
    def get_moral_interval(self, confidence: float = 0.95) -> Tuple[float, float]:
        """Get confidence interval for moral scores."""
        if not self.moral_scores:
            return (-2.0, 2.0)
        
        alpha = 1 - confidence
        interval = stats.t.interval(
            confidence=confidence,
            df=len(self.moral_scores)-1,
            loc=self.moral_mean,
            scale=self.moral_std/np.sqrt(len(self.moral_scores))
        )
        return (max(-2.0, interval[0]), min(2.0, interval[1]))
    
    def get_pdf_data(self, dim: str = 'power', points: int = 100) -> Dict[str, List[float]]:
        """
        Get probability density function data for plotting.
        
        Args:
            dim: Dimension to get PDF for ('power' or 'moral')
            points: Number of points to calculate
            
        Returns:
            Dictionary with 'x' and 'y' values for plotting
        """
        x = np.linspace(-2, 2, points)
        
        if dim == 'power':
            y = [self.power_pdf(xi) for xi in x]
        else:
            y = [self.moral_pdf(xi) for xi in x]
            
        return {'x': x.tolist(), 'y': y}
    
    def probability_of_score(self, power_score: float, moral_score: float) -> float:
        """
        Calculate joint probability density for a given power and moral score.
        
        Assuming independence between dimensions for simplicity.
        """
        return self.power_pdf(power_score) * self.moral_pdf(moral_score)
    
    def score_significance(self, power_score: float, moral_score: float) -> Tuple[float, float]:
        """
        Calculate the significance (p-value) for an observed score.
        
        This calculates how "unusual" a particular score combination is 
        compared to the expected distribution.
        
        Returns:
            Tuple of (power_p_value, moral_p_value)
        """
        # Two-tailed p-value for power score
        power_p = 2 * min(
            self.power_cdf(power_score),
            1 - self.power_cdf(power_score)
        )
        
        # Two-tailed p-value for moral score
        moral_p = 2 * min(
            self.moral_cdf(moral_score),
            1 - self.moral_cdf(moral_score)
        )
        
        return (power_p, moral_p)
    
    def combined_significance(self, power_score: float, moral_score: float) -> float:
        """
        Calculate combined p-value for both dimensions using Fisher's method.
        
        This combines p-values from both dimensions to get an overall measure
        of how unusual the sentiment is.
        """
        power_p, moral_p = self.score_significance(power_score, moral_score)
        
        # Fisher's method for combining p-values
        fisher_stat = -2 * (np.log(power_p) + np.log(moral_p))
        combined_p = 1 - stats.chi2.cdf(fisher_stat, df=4)
        
        return combined_p


class HierarchicalSentimentModel:
    """
    Hierarchical model for entity sentiment analysis across multiple levels.
    
    This model represents sentiment distributions at different levels:
    - Global (all news sources)
    - National (news sources within a country)
    - Source (individual news outlet)
    
    It enables statistical comparisons of a given sentiment against the expected
    distributions at each level.
    """
    
    def __init__(self):
        # Distribution for all entities across all sources
        self.global_distributions = {}
        
        # Distribution by country/region
        self.national_distributions = {}
        
        # Distribution by individual source
        self.source_distributions = {}
    
    def add_entity_observation(self, 
                              entity_name: str, 
                              entity_type: str,
                              power_score: float, 
                              moral_score: float,
                              source: str,
                              country: str):
        """
        Add a new entity sentiment observation to the model.
        
        Args:
            entity_name: Name of the entity
            entity_type: Type of entity (person, country, org, etc.)
            power_score: Power dimension score (-2 to +2)
            moral_score: Moral dimension score (-2 to +2)
            source: News source name
            country: Country/region of the news source
        """
        # Entity key combines name and type
        entity_key = f"{entity_name}|{entity_type}"
        
        # Source key
        source_key = f"{source}|{country}"
        
        # Add to global distribution
        if entity_key not in self.global_distributions:
            self.global_distributions[entity_key] = SentimentDistribution()
        self.global_distributions[entity_key].add_scores(power_score, moral_score)
        
        # Add to national distribution
        if country not in self.national_distributions:
            self.national_distributions[country] = {}
        
        if entity_key not in self.national_distributions[country]:
            self.national_distributions[country][entity_key] = SentimentDistribution()
        self.national_distributions[country][entity_key].add_scores(power_score, moral_score)
        
        # Add to source distribution
        if source_key not in self.source_distributions:
            self.source_distributions[source_key] = {}
        
        if entity_key not in self.source_distributions[source_key]:
            self.source_distributions[source_key][entity_key] = SentimentDistribution()
        self.source_distributions[source_key][entity_key].add_scores(power_score, moral_score)
    
    def get_entity_global_distribution(self, 
                                     entity_name: str, 
                                     entity_type: str) -> Optional[SentimentDistribution]:
        """Get the global distribution for an entity."""
        entity_key = f"{entity_name}|{entity_type}"
        return self.global_distributions.get(entity_key)
    
    def get_entity_national_distribution(self, 
                                       entity_name: str, 
                                       entity_type: str,
                                       country: str) -> Optional[SentimentDistribution]:
        """Get the national distribution for an entity."""
        entity_key = f"{entity_name}|{entity_type}"
        if country not in self.national_distributions:
            return None
        return self.national_distributions[country].get(entity_key)
    
    def get_entity_source_distribution(self, 
                                     entity_name: str, 
                                     entity_type: str,
                                     source: str,
                                     country: str) -> Optional[SentimentDistribution]:
        """Get the source-specific distribution for an entity."""
        entity_key = f"{entity_name}|{entity_type}"
        source_key = f"{source}|{country}"
        if source_key not in self.source_distributions:
            return None
        return self.source_distributions[source_key].get(entity_key)

    def analyze_entity_sentiment(self,
                               entity_name: str,
                               entity_type: str,
                               power_score: float,
                               moral_score: float,
                               source: str,
                               country: str) -> Dict[str, Any]:
        """
        Analyze how unusual a sentiment is compared to different reference distributions.
        
        Args:
            entity_name: Name of the entity
            entity_type: Type of entity (person, country, org, etc.)
            power_score: Power dimension score (-2 to +2)
            moral_score: Moral dimension score (-2 to +2)
            source: News source name
            country: Country/region of the news source
            
        Returns:
            Dictionary with analysis results including significance values
        """
        entity_key = f"{entity_name}|{entity_type}"
        result = {
            "entity": entity_name,
            "type": entity_type,
            "power_score": power_score,
            "moral_score": moral_score,
            "source": source,
            "country": country
        }
        
        # Get available distributions
        global_dist = self.get_entity_global_distribution(entity_name, entity_type)
        national_dist = self.get_entity_national_distribution(entity_name, entity_type, country)
        source_dist = self.get_entity_source_distribution(entity_name, entity_type, source, country)
        
        # Calculate significance against global distribution
        if global_dist and global_dist.count > 5:
            power_p, moral_p = global_dist.score_significance(power_score, moral_score)
            result["global_power_p"] = power_p
            result["global_moral_p"] = moral_p
            result["global_significance"] = global_dist.combined_significance(power_score, moral_score)
            result["global_count"] = global_dist.count
            result["global_power_mean"] = global_dist.power_mean
            result["global_moral_mean"] = global_dist.moral_mean
        
        # Calculate significance against national distribution
        if national_dist and national_dist.count > 5:
            power_p, moral_p = national_dist.score_significance(power_score, moral_score)
            result["national_power_p"] = power_p
            result["national_moral_p"] = moral_p
            result["national_significance"] = national_dist.combined_significance(power_score, moral_score)
            result["national_count"] = national_dist.count
            result["national_power_mean"] = national_dist.power_mean
            result["national_moral_mean"] = national_dist.moral_mean
        
        # Calculate significance against source distribution
        if source_dist and source_dist.count > 5:
            power_p, moral_p = source_dist.score_significance(power_score, moral_score)
            result["source_power_p"] = power_p
            result["source_moral_p"] = moral_p
            result["source_significance"] = source_dist.combined_significance(power_score, moral_score)
            result["source_count"] = source_dist.count
            result["source_power_mean"] = source_dist.power_mean
            result["source_moral_mean"] = source_dist.moral_mean
        
        return result
    
    def calculate_composite_score(self, entity_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate a composite unusualness score for an article based on all its entities.
        
        This combines p-values from all entity analyses to determine how unusual
        the overall sentiment pattern is compared to typical coverage.
        
        Args:
            entity_results: List of entity analysis results from analyze_entity_sentiment
            
        Returns:
            Dictionary with composite score information
        """
        # Collect p-values
        global_p_values = []
        national_p_values = []
        
        for result in entity_results:
            if "global_significance" in result:
                global_p_values.append(result["global_significance"])
            
            if "national_significance" in result:
                national_p_values.append(result["national_significance"])
        
        # Calculate composite scores using Fisher's method
        composite_score = {}
        
        if global_p_values:
            # Fisher's method for combining p-values
            fisher_stat = -2 * sum(np.log(p) for p in global_p_values)
            global_composite_p = 1 - stats.chi2.cdf(fisher_stat, df=2*len(global_p_values))
            composite_score["global_p_value"] = global_composite_p
            composite_score["global_percentile"] = global_composite_p * 100
        
        if national_p_values:
            # Fisher's method for combining p-values
            fisher_stat = -2 * sum(np.log(p) for p in national_p_values)
            national_composite_p = 1 - stats.chi2.cdf(fisher_stat, df=2*len(national_p_values))
            composite_score["national_p_value"] = national_composite_p
            composite_score["national_percentile"] = national_composite_p * 100
        
        # Overall composite score (equally weighting national and global)
        if global_p_values and national_p_values:
            composite_score["composite_p_value"] = (composite_score["global_p_value"] + 
                                                  composite_score["national_p_value"]) / 2
            composite_score["percentile"] = (composite_score["global_percentile"] + 
                                           composite_score["national_percentile"]) / 2
        elif global_p_values:
            composite_score["composite_p_value"] = composite_score["global_p_value"]
            composite_score["percentile"] = composite_score["global_percentile"]
        elif national_p_values:
            composite_score["composite_p_value"] = composite_score["national_p_value"]
            composite_score["percentile"] = composite_score["national_percentile"]
        else:
            composite_score["composite_p_value"] = 0.5
            composite_score["percentile"] = 50
        
        return composite_score