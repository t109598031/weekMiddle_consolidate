

class S3:
    def __init__(self,s3Region,bucketName,aws_access_key_id,aws__secret_access_key):
        self.__s3Region = s3Region
        self.__bucketName = bucketName
        self.__aws_access_key_id = aws_access_key_id
        self.__aws__secret_access_key = aws__secret_access_key
        self.__client = boto3.client('s3',
                                     aws_access_key_id=aws_access_key_id,
                                     aws_secret_access_key=aws_secret_access_key,
                                     region_name=region_name)
    def storeJson(self,key,body):
        self.__client.put_object(Body=str(json.dumps(body)),
                                Bucket = self.__bucketName,
                                Key = key)
    def readJson(self,key):
        body = self.__client.get_object(Bucket = self.__bucketName,
                                          Key = key)['Body']
        jsonString = body.read().decode('utf-8')
        jsonData = json.loads(jsonString) #{"imageData":[],memberIdList}
        body.close()
        return jsonData
    def listObjects(self,keyword):
        listObjectsResponse = self.__client.list_objects_v2(Bucket=self.__bucketName,
                                                                 StartAfter=keyword)
        return listObjectsResponse
    def storeImage(self,image,fileName):
        image = self.__dataModel["frame"]["openCV"]["imageBase64"]
        image = base64.b64decode(image)
        #fileName = "image" + self.__dataModel["frame"]["captureResult"]["id"]
        self.__client.put_object(ACL='public-read',
                                 Body=image,
                                 Bucket=self.__bucketName,
                                 Key=fileName ,
                                 ContentEncoding='base64',
                                 ContentType='image/jpeg')
        
class Rekognition:
    def __init__(self,region,aws_access_key_id,aws_secret_access_key,image):
        self.__region = region
        self.__aws_access_key_id = aws_access_key_id
        self.__aws_secret_access_key = aws_secret_access_key
        self.__client = boto3.client('rekognition',
                                     aws_access_key_id=aws_access_key_id,
                                     aws_secret_access_key=aws_secret_access_key,
                                     region_name=region_name)
        self.__image = image
        self.__rekognitionModel = {}
    def faceDetect(self):
        binaryImage = base64.b64decode(self.__image)
        faceDetectResponse = self.__client.detect_faces(Image={'Bytes': binaryImage})
        return faceDetectResponse
    def faceSearch(self,collection,image,threshold):
        faceMatchResponse = self.__client.search_faces_by_image(CollectionId = self.__collectionId,
                                                                Image={'Bytes':image},
                                                                FaceMatchThreshold=threshold,
                                                                MaxFaces=1)
        return faceMatchResponse
    def getModel(self):
        return self.__rekognitionModel
    
class FaceSearch:
    def __init__(self,config,dataModel,s3,rekognition,collectionId,memberFaceFileName):
        self.__config = config
        self.__dataModel = dataModel
        self.__s3 = s3
        self.__rekognition = rekognition
        self.__collectionId = collectionId
        self.__memberFaceFileName = memberFaceFileName
        self.__memberFaceList = {}
    def signInFace(self):
        image = self.__dataModel["frame"]["openCV"]["imageBase64"]
        binaryImage = base64.b64decode(self.__dataModel["frame"]["openCV"]["imageBase64"])
        faceDetectResponse = self.__rekognition.faceDetect()

        personList = []
        personCounter = len(faceDetectResponse["FaceDetails"])
        
        faceIdList = []
        faceBoundingBoxList = []
        faceImageIdList = []
        faceImageUrlList = []
        registrationImageList = [] #成員已註冊的人臉資料
        registrationImageCounter = 0 #成員已註冊的人臉數
        matchedImageCounter = 0 #匹配到的成員已註冊人臉數
        memberCounter = 0
        sumSimilarity = 0
        averageSimilarity = 0
        serialNo = 0 #多張人臉需要編號
        threshold = 80
        self.__dataModel["signInResult"] = {}
        self.__dataModel["signInResult"]["personList"] = []
        self.__dataModel["frame"]["personList"] = []
        self.__dataModel["frame"]["sourceImage"]["personCount"] = personCounter
        
        if len(faceDetectResponse["FaceDetails"]) >= 1: #複數人臉
            for face in faceDetectResponse["FaceDetails"]:
                faceBoundingBoxList.append(face["BoundingBox"])
            binaryImage = base64.b64decode(image)
            faceImageList = image_splite(binaryImage,faceBoundingBoxList) #切割
            for image in faceImageList:
                fileName = 'face' + str(self.__dataModel["frame"]["captureResult"]["timestamp"]) + str(serialNo) + '.jpg'
                faceImageUrlList = self.s3._storeFaceImage(image,fileName)
                serialNo += 1
            serialNo = 0
            ##############################
            for faceImage in faceImageList: 
                searchFaceResponse=self.rekognition.faceSearch(self.__collectionId, #成員與簽到人臉匹配
                                                                Image={'Bytes':faceImage},
                                                                FaceMatchThreshold=threshold,
                                                                MaxFaces=10)
                faceImageIdList = [] #清空
                personList = {} #清空
                matchedImageCounter = len(searchFaceResponse["FaceMatches"]) #重新判斷
                registrationImageList = [] #清空
                if len(searchFaceResponse["FaceMatches"]) != 0:
                    memberFaceListResponse = self.s3.listobjects(searchFaceResponse["FaceMatches"][0]["Face"]["ExternalImageId"])
                    for face in memberFaceListResponse["Contents"]: #成員所有已註冊的人臉數
                        uid,faceImageId = face["Key"].split('_')[0],face["Key"].split('_')[1]
                        uid = uid.split('/')[1]
                        if uid == searchFaceResponse["FaceMatches"][0]["Face"]["ExternalImageId"]: #根據對應的成員id將對應成員的人臉加入list
                            faceImageIdList.append(faceImageId)
                    registrationImageCounter = len(faceImageIdList)
                    sumSimilarity = 0 #重新計算
                    for face in searchFaceResponse["FaceMatches"]: #成員與簽到人臉匹配(條件)
                        if face["Similarity"] > 70 and face["Face"]["FaceId"] + '.jpg' in faceImageIdList:
                            registrationModel = {}
                            faceImageUrl = 'https://' + self.s3.__bucketName + '.s3-' + self.s3.__region_name + '.amazonaws.com/' + searchFaceResponse["FaceMatches"][0]["Face"]["ExternalImageId"] + '_' + face["Face"]["FaceId"] + ".jpg"
                            faceImageUrlList.append(faceImageUrl)
                            faceIdList.append(face["Face"]["FaceId"])
                            sumSimilarity += face["Similarity"]
                            try:
                                timestamp = next(member for member in self.__memberFaceList["imageData"] if member["faceId"] == face["Face"]["FaceId"])["timestamp"]
                            except StopIteration: #上面的寫法會剛好超出list長度1 所以用try-except去忽略此錯誤
                                print("StopIteration stop")
                            registrationModel["imageUrl"] = faceImageUrl #faceImageUrlList[serialNo]
                            registrationModel["faceId"] = face["Face"]["FaceId"]
                            registrationModel["similarity"] = face["Similarity"]
                            registrationModel["timestamp"] = timestamp
                            registrationImageList.append(registrationModel)
                        """if searchFaceResponse["FaceMatches"][0]["Face"]["ExternalImageId"] not in memberList:
                            memberList.append(searchFaceResponse["FaceMatches"][0]["Face"]["ExternalImageId"])"""
                        
                    averageSimilarity = sumSimilarity / len(registrationImageList)    
                    self.__dataModel["signInResult"]["personList"].append({
                                                                            "isMember":True,
                                                                            "memberId":searchFaceResponse["FaceMatches"][0]["Face"]["ExternalImageId"],
                                                                            "registrationImageCount":len(faceImageIdList),
                                                                            "matchedImageCount":matchedImageCounter,
                                                                            "averageSimilarity":averageSimilarity
                                                                        })
                    
                    fileName = self.__faceBucketSubPathList[1] + '/face' + str(self.__dataModel["frame"]["captureResult"]["timestamp"]) + str(serialNo) + '.jpg'
                    serialNo += 1
                    memberCounter += 1
                    personList={
                                "sourceFaceImage":{"imageUrl":'https://' + self.s3.__bucketName + '.s3-' + self.s3.__region_name + '.amazonaws.com/' + fileName,
                                                    "averageSimilarity": averageSimilarity},
                                "registrationImageList":registrationImageList,
                                }
                    self.__dataModel["frame"]["personList"].append(personList)
                elif len(searchFaceResponse["FaceMatches"]) ==0:
                    self.__dataModel["signInResult"]["personList"].append({
                                                                            "isMember":False
                                                                        })
                    serialNo += 1
            self.__dataModel["signInResult"]["personCount"] = personCounter
            self.__dataModel["signInResult"]["memberCount"] = memberCounter
            self.__dataModel["signInResult"]["notMemberCount"] = self.__dataModel["signInResult"]["personCount"] - self.__dataModel["signInResult"]["memberCount"]
            self.__dataModel["signInResult"]["timestamp"] = self.__dataModel["frame"]["captureResult"]["timestamp"]
            self.__dataModel["frame"]["sourceImage"]["personCount"] = len(faceDetectResponse["FaceDetails"])
    
    def spliteImage(self,boundingboxes):
        imagelist = []
        image = np.fromstring(self.__dataModel["frame"]["openCV"]["imageBase64"],np.uint8)
        image = cv2.imdecode(image,cv2.IMREAD_COLOR)
        size = image.shape
        height , width = size[0],size[1]
        for BBox in boundingboxes:
            print("---------------")
            print(BBox)
            upperLeftPointX = int(BBox['Left']*width)
            upperLeftPointY = int(BBox['Top']*height)               
            lowerRightPointX = int((BBox['Left']+BBox['Width'])*width)
            lowerRightPointY = int((BBox['Top']+BBox['Height'])*height)
            cut_image = copy.deepcopy(image)[upperLeftPointY:lowerRightPointY,upperLeftPointX:lowerRightPointX]
            cut_image = base64.b64encode(cv2.imencode('.jpg', cut_image)[1]).decode() 
            cut_image = base64.b64decode(cut_image)

            imagelist.append(cut_image)

        print(len(imagelist))
        print("cut finish")
        return imagelist
    def _createFaceData(self,binaryImage,uid):
        faceIdList = []
        response=self.__client.index_faces(CollectionId=self.__collectionId,
                                    Image={'Bytes':binaryImage},
                                    MaxFaces=1,
                                    ExternalImageId=uid,
                                    QualityFilter="AUTO",
                                    DetectionAttributes=['ALL'])
        for face in response['FaceRecords']:
            faceIdList.append(face['Face']['FaceId'])
        return faceIdList
    def getModel(self):
        return self.__dataModel
        
