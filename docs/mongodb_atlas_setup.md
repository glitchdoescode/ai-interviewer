# Setting Up MongoDB Atlas for AI Interviewer

This guide will help you connect your AI Interviewer application to MongoDB Atlas cloud database service instead of a locally hosted MongoDB instance.

## Why MongoDB Atlas?

- **Cloud-based solution**: No need to maintain your own MongoDB server
- **Free tier available**: Includes 512MB storage, sufficient for testing
- **Automatic backups**: Data is automatically backed up
- **Security**: Built-in security features like IP whitelisting, VPC peering, and encryption at rest
- **Scalability**: Easily scale as your data needs grow

## Step 1: Create a MongoDB Atlas Account

1. Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) and click "Try Free"
2. Register for a new account or sign in if you already have one
3. Complete the initial setup questions

## Step 2: Create a Cluster

1. In the Atlas dashboard, click "Create" to set up a new cluster
2. Select your preferred cloud provider (AWS, Google Cloud, or Azure)
3. Choose the "Free Tier" option (M0 Sandbox)
4. Select a region closest to your application's hosting location
5. Click "Create Cluster" (this may take a few minutes to provision)

## Step 3: Configure Database Access

1. In the left sidebar, go to "Database Access" under Security
2. Click "Add New Database User"
3. Create a username and password (save these securely)
4. Set appropriate permissions (for testing, "Atlas admin" is sufficient)
5. Click "Add User"

## Step 4: Configure Network Access

1. In the left sidebar, go to "Network Access" under Security
2. Click "Add IP Address"
3. To allow access from your current IP, click "Add Current IP Address"
4. For production, add specific IP addresses that should have access
5. For development, you can temporarily use "Allow Access from Anywhere" (0.0.0.0/0)
6. Click "Confirm"

## Step 5: Get Your Connection String

1. Return to the Clusters view and click "Connect" on your cluster
2. Select "Connect your application"
3. Choose your driver version (Python 3.6 or later)
4. Copy the connection string shown

## Step 6: Update AI Interviewer Configuration

1. Copy your `.env.example` file to `.env` if you haven't already:
   ```
   cp config.env.example .env
   ```

2. Edit the `.env` file and update the MongoDB connection string:
   ```
   MONGODB_URI=mongodb+srv://<username>:<password>@<cluster-name>.<subdomain>.mongodb.net/?retryWrites=true&w=majority
   ```
   
   Replace:
   - `<username>` and `<password>` with your database user credentials
   - `<cluster-name>.<subdomain>` with your actual cluster address

3. Keep the other MongoDB configuration settings as they are:
   ```
   MONGODB_DATABASE=ai_interviewer
   MONGODB_SESSIONS_COLLECTION=interview_sessions
   MONGODB_METADATA_COLLECTION=interview_metadata
   MONGODB_CHECKPOINT_DB=ai_interviewer
   MONGODB_CHECKPOINT_COLLECTION=checkpoints
   ```

## Step 7: Test the Connection

1. Run your application with the updated configuration
2. If configured correctly, the application should connect to MongoDB Atlas
3. Check your application logs for successful connection messages

## Troubleshooting

- **Connection failures**: Ensure your IP is in the Network Access allowlist
- **Authentication failures**: Verify username and password in the connection string
- **Database errors**: Make sure your database user has sufficient permissions
- **Timeout issues**: Check network connectivity and firewall settings

## Production Considerations

1. Use environment-specific connection strings for development, testing, and production
2. Consider upgrading to a paid tier for production usage with higher storage and performance
3. Set up database alerts for resource utilization
4. Implement proper credential management (don't commit credentials to version control)
5. Consider enabling additional security features like:
   - VPC peering
   - Private endpoints
   - Database auditing
   - Multi-factor authentication

## Additional Resources

- [MongoDB Atlas Documentation](https://docs.atlas.mongodb.com/)
- [MongoDB Connection String URI Format](https://docs.mongodb.com/manual/reference/connection-string/)
- [MongoDB Python Driver Documentation](https://docs.mongodb.com/drivers/pymongo/) 