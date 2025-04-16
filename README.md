# Predicting Train Arrivals

We're setting up a data pipeline to optimize CTA train arrival predictions at stations located near terminal stations. Currently, CTA only starts live tracking a train after it has left the terminal. As a result, arrival predictions at nearby stations (like Noyes, Central, or South Blvd) are practically useless. You typically only find out a train is approaching when it's just 2 minutes away.

However, we know that trains heading in the opposite direction usually wait at the terminal station before starting their next trip. With enough historical data, we can identify patterns and attempt to generate expected arrival schedules for these stations.

The class `CTATrainDataParser` is responsible for safely reading the data collected from the `EL Tracker` application. The function `get_entries_by_station` returns a tuple that pairs the timestamp of the arrival request with the corresponding train arrival response. From there, we extract features to feed into a learning algorithm.