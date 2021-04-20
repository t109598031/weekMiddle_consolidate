

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
    
class FaceDetect:
    def __init__(self,config,dataModel,s3,rekognition,collectionId,memberFaceFileName):
        self.__config = config
        self.__dataModel = dataModel
        self.__s3 = s3
        self.__rekognition = rekognition
        self.__collectionId = collectionId
        self.__memberFaceFileName = memberFaceFileName
        self.__memberFaceList = {}
    def registeredFace(self):
        binaryImage = base64.b64decode(self.__dataModel["frame"]["openCV"]["imageBase64"])
        #faceDetectResponse = self.__client.detect_faces(Image={'Bytes': binaryImage})
        faceDetectResponse = self.s3.faceDetect()
        
        threshold = self.__dataModel["config"]["threshold"]
        faceCount = len(faceDetectResponse["FaceDetails"])
        imageList = []
        memeberCounter = 0
        sumSimilarity = 0
        self.__dataModel["frame"]["memberList"] = [] #建立list
        for face in faceDetectResponse["FaceDetails"]:
            faceModel = {}
            imageList = spliteImage(binaryImage,[face["BoundingBox"]])
            
            faceMatchResponse = self.__client.search_faces_by_image(CollectionId = self.__collectionId,
                            Image={'Bytes':imageList[0]},
                            FaceMatchThreshold=threshold,
                            MaxFaces=3)
            faceMatchResponse = self.__rekognition.faceSearch(self.__collectionId,imageList[0],threshold)
            if len(faceMatchResponse["FaceMatches"]) == 0:  #新成員
                uid = str(uuid.uuid1()) #產生新成員的memberId
                faceIdList = self._createFaceData(imageList[0],uid)
                fileName = uid + '_' + faceId + '.jpg'
                faceImageUrlList = self._storeImage(imageList[0],fileName)
                memberFaceModel = {
                    "uid":uid,
                    "faceId":faceIdList[0],
                    "faceImageUrl":faceImageUrlList[0],
                    "timestamp":self.__dataModel["frame"]["captureResult"]["timestamp"]
                }
                self.__memberFaceList["imageData"].append(memberFaceModel)
                self.__memberFaceList["memberIdList"].append(faceModel["uid"])
                '''self.__s3Client.put_object(Body=str(json.dumps(self.__memberFaceList)),
                                    Bucket = self.__memberFaceListBucketName,
                                    Key = self.__memberFaceFileName)'''
                #
                self.s3.storeJson(self.__memberFaceFileName,str(json.dumps(self.__memberFaceList)))
                faceModel["sourceFaceImage"] = {
                                                "imageUrl":faceImageUrlList[0],
                                                "averageSimilarity":100
                                            }
                faceModel["registrationImageList"].append({
                                                        "imageUrl":imageUrl,
                                                        "faceId":faceImageUrlList[0],
                                                        "similarity":[100.0],#新成員第一張人臉直接給定相似度100%(因為在search_faces_by_image時沒有該成員的人臉)
                                                        "timestamp":self.__dataModel["frame"]["captureResult"]["timestamp"]
                                                    })
                self.__dataModel["frame"]["memberList"].append(faceModel)
                self.__dataModel["frame"]["registrationResult"] = {}
                self.__dataModel["frame"]["registrationResult"] = {
                                                                    "memberCount":len(self.__memberFaceList["memberList"]),    #成員總數
                                                                    "personCount":len(faceDetectResponse["FaceDetails"]),    #來源人數
                                                                    "memberList":[]
                                                                }
                self.__dataModel["frame"]["registrationResult"]["memberList"].append({
                                                                                        "memberId":uid,
                                                                                        "registrationImageCount":1,
                                                                                        "matchedImageCount":1,
                                                                                        "averageSimilarity":100.0,
                                                                                        "registrationImageList":[{
                                                                                            "faceId":faceIdList[0],
                                                                                            "similarity":100.0,
                                                                                            "timestamp":self.__dataModel["frame"]["captureResult"]["timestamp"]
                                                                                        }]
                                                                                    })
            else: #已經註冊過
                faceIdList = [] #先清空
                faceImageIdList = []
                faceImageUrlList = []
                faceModel["uid"] = faceMatchResponse["FaceMatches"][0]["Face"]["ExternalImageId"] #取出匹配到的成員id
                
                faceImageIdList = self._createFaceData(imageList[0],faceModel["uid"])
                fileName = faceModel["uid"] + '_' + faceModel["newFaceId"] + '.jpg'
                faceImageUrlList = self._storeImage(imageList[0],fileName) ###
                memberFaceModel = {
                    "uid":faceModel["uid"],
                    "faceId":faceImageIdList[0],
                    "faceImageUrl":faceImageUrlList[0],
                    "timestamp":self.__dataModel["frame"]["captureResult"]["timestamp"]
                }
                self.__memberFaceList["imageData"].append(memberFaceModel)
                """memberFaceListResponse = self.__s3Client.list_objects_v2(Bucket=self.__faceBucketName,
                                                                     StartAfter=self.__faceBucketSubPathList[0] + faceModel["uid"])"""
                ###
                memberFaceListResponse = self.s3.listObjects(faceModel["uid"])
                registrationImageList = []
                faceModel["registrationResult"] = {}
                
                for face in memberFaceListResponse["Contents"]:
                    uid,faceImageId = face["Key"].split('_')[0],face["Key"].split('_')[1]
                    uid = uid.split('/')[1]
                    if uid ==faceModel["uid"]:
                        faceImageIdList.append(faceImageId)
                faceModel["registrationImageCount"] = len(faceImageIdList)
                for face in faceMatchResponse["FaceMatches"]:
                    if face["Similarity"] > 90 and face["Face"]["FaceId"] + '.jpg' in faceImageIdList: #相似度90以上且檔案名稱含有該成員uid才加入至list中
                        faceImageUrl = 'https://' + self.s3.__bucketName + '.s3-' + self.s3.__region_name + '.amazonaws.com/' + faceModel["uid"] + '_' + face["Face"]["FaceId"] + ".jpg"
                        faceImageUrlList.append(faceImageUrl)
                        faceIdList.append(face["Face"]["FaceId"])
                        sumSimilarity += face["Similarity"]
                        try:
                            timestamp = next(member for member in self.__memberFaceList["imageData"] if member["faceId"] == face["Face"]["FaceId"])["timestamp"]
                        except StopIteration: #上面的寫法會剛好超出list長度1 所以用try-except去忽略此錯誤
                                print("StopIteration stop")
                        registrationImageList.append({
                                                        "imageUrl":faceImageUrl,
                                                        "faceId":face["Face"]["FaceId"],
                                                        "similarity":face["Similarity"],
                                                        "timestamp":timestamp
                                                    })
                        
                        faceModel["registrationResult"]["memberList"].append({
                                                                            "memberId":faceMatchResponse["FaceMatches"][0]["Face"]["ExternalImageId"],
                                                                            "registrationImageCount":len(faceMatchResponse["FaceMatches"]),
                                                                            "matchedImageCount":len(faceIdList),
                                                                            "averageSimilarity":sumSimilarity / len(faceIdList),
                                                                            "registrationImageList":[{
                                                                                "faceId":face["Face"]["FaceId"],
                                                                                "similarity":face["Similarity"],
                                                                                "timestamp":next(member for member in self.__memberFaceList["imageData"] if member["faceId"] == regModel["faceId"])["timestamp"]
                                                                            }]
                                                                        })
                    faceModel["memberList"].append({
                                                        "sourceFaceImage":{
                                                            "imageUrl":faceImageUrlList[0],
                                                            "averageSimilarity":sumSimilarity / len(faceIdList)
                                                        },
                                                        "registrationImageList":registrationImageList
                                                    })
                faceModel["registrationResult"]["memberCount"] = len(self.__memberFaceList["memberIdList"])
                faceModel["registrationResult"]["personCount"] = len(faceDetectResponse["FaceDetails"])
            self.__dataModel["frame"]["registrationResult"] = faceModel
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
        
